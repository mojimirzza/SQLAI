"""
Baseline Enrichment Models
--------------------------
Structured data for comparing current results against historical baselines.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BaselineMetrics:
    """
    Historical context for a single metric value.
    All computed deterministically via SQL — zero LLM usage.
    """
    # Core current value
    current_value: float | None = None
    current_unit: str = ""

    # Day-over-day
    yesterday_value: float | None = None
    yesterday_delta_pct: float | None = None

    # Week-over-week (same day of week)
    last_week_same_day_value: float | None = None
    last_week_same_day_delta_pct: float | None = None

    # 7-day rolling average
    avg_7d_value: float | None = None
    avg_7d_delta_pct: float | None = None

    # 30-day rolling average
    avg_30d_value: float | None = None
    avg_30d_delta_pct: float | None = None

    # 30-day extremes
    max_30d_value: float | None = None
    min_30d_value: float | None = None

    # Trend over last 7 days
    trend_7d: str = "stable"  # "rising" | "falling" | "stable"
    trend_7d_slope: float | None = None  # daily change rate

    # Anomaly detection (simple threshold-based)
    anomaly_flag: bool = False
    anomaly_severity: str = "none"  # "none" | "low" | "medium" | "high"
    anomaly_reason: str | None = None

    # Raw time-series for charting (last 30 days)
    daily_series_30d: list[dict[str, Any]] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Format as concise text for LLM prompt injection."""
        lines = ["=== BASELINE CONTEXT ==="]
        if self.current_value is not None:
            lines.append(f"Current: {self.current_value:,.0f} {self.current_unit}".strip())

        if self.yesterday_delta_pct is not None:
            emoji = "📉" if self.yesterday_delta_pct < -10 else "📈" if self.yesterday_delta_pct > 10 else "➡️"
            lines.append(f"vs Yesterday: {self.yesterday_value:,.0f} ({self.yesterday_delta_pct:+.1f}%) {emoji}")

        if self.last_week_same_day_delta_pct is not None:
            lines.append(f"vs Last Week Same Day: {self.last_week_same_day_value:,.0f} ({self.last_week_same_day_delta_pct:+.1f}%)")

        if self.avg_30d_delta_pct is not None:
            lines.append(f"vs 30-Day Average: {self.avg_30d_value:,.0f} ({self.avg_30d_delta_pct:+.1f}%)")

        if self.max_30d_value is not None:
            lines.append(f"30-Day Range: {self.min_30d_value:,.0f} – {self.max_30d_value:,.0f}")

        if self.trend_7d != "stable":
            lines.append(f"7-Day Trend: {self.trend_7d} (slope: {self.trend_7d_slope:+.1f}/day)")

        if self.anomaly_flag:
            lines.append(f"⚠️ ANOMALY DETECTED ({self.anomaly_severity}): {self.anomaly_reason}")

        lines.append("=== END BASELINE ===")
        return "\n".join(lines)
