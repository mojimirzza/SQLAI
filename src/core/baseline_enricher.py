"""
Baseline Enricher — Simplified Pre-calculated Edition
------------------------------------------------------
Queries pre-calculated summary table for instant baseline context.
Falls back to result-based computation if summary table unavailable.

Key simplification: ONE query instead of 6. <50ms total.
"""
import re
from datetime import date, timedelta
from typing import Any

from core.baseline_models import BaselineMetrics
from ports.sql_executor_port import SQLExecutorPort


# Extract date_in_sk filter from SQL
DATE_FILTER_RE = re.compile(
    r"fact_transaction\.date_in_sk\s*>=\s*(\d+)\s+AND\s+fact_transaction\.date_in_sk\s*<\s*(\d+)"
)

# Extract server name from SQL
SERVER_FILTER_RE = re.compile(
    r"dim_server\.server_name\s*=\s*['']([^'']+)['']"
)


class BaselineEnricher:
    """
    Simplified baseline enrichment.

    Strategy:
    1. Try to query pre-calculated fact_txn_daily_summary table
    2. If unavailable, compute from execution result (time-series only)
    3. Always check SLA thresholds
    """

    def __init__(self, sql_executor: SQLExecutorPort):
        self.sql_executor = sql_executor
        self._has_summary_table = None  # cached

    def enrich(self, intent, generated, execution) -> BaselineMetrics:
        """Main entry. Returns BaselineMetrics with context."""

        # Extract current value
        current_value = self._extract_metric_value(execution.rows, generated.metric_used)
        if current_value is None:
            return BaselineMetrics()

        baseline = BaselineMetrics(current_value=current_value)

        # Extract query dimensions from SQL
        date_range = self._extract_date_range(generated.sql)
        server_name = self._extract_server_name(generated.sql)
        metric_name = self._map_metric_name(generated.metric_used)

        # Strategy 1: Pre-calculated summary table (fastest)
        if self._summary_table_exists():
            precomputed = self._lookup_summary_table(date_range, server_name, metric_name)
            if precomputed:
                return precomputed

        # Strategy 2: Compute from result rows (time-series queries)
        if self._is_time_series_query(generated):
            return self._compute_from_results(execution.rows, baseline)

        # Strategy 3: Minimal fallback (just SLA check)
        self._check_sla(baseline, metric_name)
        return baseline

    # ------------------------------------------------------------------
    # Strategy 1: Pre-calculated summary table lookup
    # ------------------------------------------------------------------

    def _summary_table_exists(self) -> bool:
        """Check if fact_txn_daily_summary exists in DuckDB. Cached."""
        if self._has_summary_table is not None:
            return self._has_summary_table

        result = self.sql_executor.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'fact_txn_daily_summary'",
            readonly=True, timeout_ms=1000
        )
        self._has_summary_table = result.success and result.rows and len(result.rows) > 0
        return self._has_summary_table

    def _lookup_summary_table(self, date_range: tuple | None, server_name: str | None,
                              metric_name: str) -> BaselineMetrics | None:
        """Compute a metric-aware baseline from daily summary rows."""
        if not date_range:
            return None
        target_date = int(date_range[0])
        safe_server = server_name.replace("'", "''") if server_name else None
        server_clause = ""
        if safe_server:
            server_clause = f"AND server_sk = (SELECT server_sk FROM dim_server WHERE server_name = '{safe_server}')"
        sql = f"""
            SELECT summary_date, txn_count, approved_count, total_amount, avg_switch_ms,
                   stuck_count, hot_card_count, error_count
            FROM fact_txn_daily_summary
            WHERE summary_date <= {target_date} {server_clause}
            ORDER BY summary_date DESC
            LIMIT 1000
        """
        result = self.sql_executor.execute(sql, readonly=True, timeout_ms=2000)
        if not result.success or not result.rows:
            return None

        rows = result.rows
        by_date: dict[int, list[dict]] = {}
        for row in rows:
            by_date.setdefault(int(row["summary_date"]), []).append(row)

        def metric_value(items: list[dict]) -> float | None:
            if not items:
                return None
            if metric_name == "txn_count":
                return float(sum((r.get("txn_count") or 0) for r in items))
            if metric_name == "approval_rate":
                txns = sum((r.get("txn_count") or 0) for r in items)
                approved = sum((r.get("approved_count") or 0) for r in items)
                return (approved * 100.0 / txns) if txns else None
            if metric_name == "total_amount":
                return float(sum((r.get("total_amount") or 0) for r in items))
            if metric_name == "avg_switch_ms":
                weights = [(float(r.get("avg_switch_ms") or 0), float(r.get("txn_count") or 0)) for r in items]
                total_w = sum(w for _, w in weights)
                return (sum(v*w for v, w in weights) / total_w) if total_w else None
            if metric_name == "stuck_count":
                return float(sum((r.get("stuck_count") or 0) for r in items))
            if metric_name == "hot_card_count":
                return float(sum((r.get("hot_card_count") or 0) for r in items))
            if metric_name == "error_count":
                return float(sum((r.get("error_count") or 0) for r in items))
            return None

        current = metric_value(by_date.get(target_date, []))
        if current is None:
            return None
        baseline = BaselineMetrics(current_value=current)

        def prior_date(days: int) -> int | None:
            from datetime import datetime
            d = datetime.strptime(str(target_date), "%Y%m%d").date() - timedelta(days=days)
            return int(d.strftime("%Y%m%d"))

        for days, attr in ((1, "yesterday_value"), (7, "last_week_same_day_value")):
            value = metric_value(by_date.get(prior_date(days), []))
            setattr(baseline, attr, value)
        if baseline.yesterday_value is not None:
            baseline.yesterday_delta_pct = self._pct_delta(current, baseline.yesterday_value)
        if baseline.last_week_same_day_value is not None:
            baseline.last_week_same_day_delta_pct = self._pct_delta(current, baseline.last_week_same_day_value)

        ordered_dates = sorted(by_date.keys(), reverse=True)
        recent = [metric_value(by_date[d]) for d in ordered_dates[:30]]
        recent = [v for v in recent if v is not None]
        if recent:
            last7 = recent[:7]
            baseline.avg_7d_value = sum(last7) / len(last7)
            baseline.avg_7d_delta_pct = self._pct_delta(current, baseline.avg_7d_value)
            baseline.avg_30d_value = sum(recent) / len(recent)
            baseline.avg_30d_delta_pct = self._pct_delta(current, baseline.avg_30d_value)
            baseline.max_30d_value = max(recent)
            baseline.min_30d_value = min(recent)
            baseline.daily_series_30d = [{"summary_date": d, "value": metric_value(by_date[d])} for d in ordered_dates[:30]]
            if len(last7) >= 2:
                baseline.trend_7d_slope = last7[0] - last7[-1]
                baseline.trend_7d = "rising" if baseline.trend_7d_slope > 0 else "falling" if baseline.trend_7d_slope < 0 else "stable"

        self._check_sla(baseline, metric_name)
        return baseline

    # ------------------------------------------------------------------
    # Strategy 2: Compute from result rows (time-series)
    # ------------------------------------------------------------------

    def _compute_from_results(self, rows: list[dict], baseline: BaselineMetrics) -> BaselineMetrics:
        """For time-series results, compute baselines from the series itself."""
        if not rows or len(rows) < 2:
            return baseline

        values = []
        for r in rows:
            vals = list(r.values())
            if vals:
                try:
                    values.append(float(vals[-1]))
                except (ValueError, TypeError):
                    pass

        if len(values) < 2:
            return baseline

        baseline.current_value = values[-1]

        if len(values) >= 2:
            baseline.yesterday_value = values[-2]
            baseline.yesterday_delta_pct = self._pct_delta(values[-1], values[-2])

        if len(values) >= 7:
            baseline.avg_7d_value = sum(values[-7:]) / 7
            baseline.avg_7d_delta_pct = self._pct_delta(values[-1], baseline.avg_7d_value)

        if len(values) >= 2:
            baseline.max_30d_value = max(values)
            baseline.min_30d_value = min(values)

        # Simple trend
        if len(values) >= 3:
            slope = values[-1] - values[-2]
            baseline.trend_7d = "rising" if slope > 0 else "falling" if slope < 0 else "stable"
            baseline.trend_7d_slope = slope

        self._check_sla(baseline, "txn_count")  # default metric
        return baseline

    # ------------------------------------------------------------------
    # SLA Check
    # ------------------------------------------------------------------

    def _check_sla(self, baseline: BaselineMetrics, metric_name: str):
        """Check SLA thresholds from metric_sla_thresholds table."""
        if not metric_name:
            return

        # Try to query SLA config (safe f-string with whitelist)
        allowed_metrics = {"txn_count", "approval_rate", "total_amount", "avg_switch_ms", "stuck_count", "hot_card_count", "error_count"}
        safe_metric = metric_name if metric_name in allowed_metrics else "txn_count"
        sla_sql = f"SELECT sla_min_value, sla_max_value FROM metric_sla_thresholds WHERE metric_name = '{safe_metric}'"
        result = self.sql_executor.execute(sla_sql, readonly=True, timeout_ms=1000)

        if not result.success or not result.rows:
            return

        row = result.rows[0]
        sla_min = row.get('sla_min_value')
        sla_max = row.get('sla_max_value')
        current = baseline.current_value

        if current is None:
            return

        # Check breach
        breached = False
        reason = None

        if sla_min is not None and current < float(sla_min):
            breached = True
            reason = f"Below SLA minimum ({sla_min})"
        elif sla_max is not None and current > float(sla_max):
            breached = True
            reason = f"Above SLA maximum ({sla_max})"

        # Simple anomaly: >30% deviation from 7-day avg
        if baseline.avg_7d_value and baseline.avg_7d_value > 0:
            deviation = abs(current - baseline.avg_7d_value) / baseline.avg_7d_value
            if deviation > 0.50:
                baseline.anomaly_flag = True
                baseline.anomaly_severity = "high"
                baseline.anomaly_reason = reason or f"{deviation*100:.0f}% deviation from 7-day average"
            elif deviation > 0.30:
                baseline.anomaly_flag = True
                baseline.anomaly_severity = "medium"
                baseline.anomaly_reason = reason or f"{deviation*100:.0f}% deviation from 7-day average"
            elif deviation > 0.15:
                baseline.anomaly_flag = True
                baseline.anomaly_severity = "low"
                baseline.anomaly_reason = reason or f"{deviation*100:.0f}% deviation from 7-day average"

        if breached and not baseline.anomaly_flag:
            baseline.anomaly_flag = True
            baseline.anomaly_severity = "medium"
            baseline.anomaly_reason = reason

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_metric_value(self, rows: list[dict] | None, metric_name: str | None) -> float | None:
        if not rows:
            return None
        row = rows[0]
        if not row:
            return None
        if metric_name and metric_name in row:
            try:
                return float(row[metric_name])
            except (ValueError, TypeError):
                pass
        vals = list(row.values())
        if vals:
            try:
                return float(vals[-1])
            except (ValueError, TypeError):
                pass
        return None

    def _extract_date_range(self, sql: str) -> tuple[int, int] | None:
        match = DATE_FILTER_RE.search(sql)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return None

    def _extract_server_name(self, sql: str) -> str | None:
        match = SERVER_FILTER_RE.search(sql)
        if match:
            return match.group(1)
        return None

    def _map_metric_name(self, metric_used: str | None) -> str:
        """Map semantic metric name to summary table column name."""
        mapping = {
            "total_transactions": "txn_count",
            "approval_rate": "approval_rate",
            "total_amount": "total_amount",
            "avg_switch_latency": "avg_switch_ms",
            "stuck_transactions": "stuck_count",
            "hot_card_count": "hot_card_count",
            "error_count": "error_count",
        }
        return mapping.get(metric_used, "txn_count")

    def _is_time_series_query(self, generated) -> bool:
        time_dims = {"year", "quarter", "month", "month_name", "day_of_month",
                     "day_of_week", "day_name", "week_of_year", "hour24", "hour12"}
        for dim_alias in generated.dimensions:
            dim_name = dim_alias.split("_")[-1] if "_" in dim_alias else dim_alias
            if dim_name in time_dims:
                return True
        return False

    @staticmethod
    def _pct_delta(current: float, baseline: float | None) -> float | None:
        if baseline is None or baseline == 0:
            return None
        return ((current - baseline) / baseline) * 100.0
