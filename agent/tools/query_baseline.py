"""
Tool: query_baseline
Reads the pre-computed baseline table for anomalies.
"""
from datetime import datetime


def query_baseline(db_path: str = "data/bank.duckdb") -> list[dict]:
    """
    Query today's unalerted anomalies from metric_daily_baseline.
    Returns list of anomaly rows.
    """
    today = int(datetime.now().strftime("%Y%m%d"))

    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB is required for the alert agent warehouse connection") from exc

    conn = duckdb.connect(db_path, read_only=True)

    rows = conn.execute("""
        SELECT 
            baseline_date,
            metric_name,
            server_sk,
            device_category,
            hour24,
            current_value,
            yest_value,
            yest_delta_pct,
            avg_7d_value,
            avg_7d_delta_pct,
            z_score,
            is_anomaly,
            anomaly_severity,
            is_sla_breach,
            sla_min_value,
            sla_max_value
        FROM metric_daily_baseline
        WHERE baseline_date = ?
          AND is_anomaly = 1
          AND alerted = 0
        ORDER BY 
            is_sla_breach DESC,
            ABS(COALESCE(z_score, 0)) DESC
    """, (today,)).fetchall()

    columns = [d[0] for d in conn.description]
    conn.close()
    return [dict(zip(columns, r)) for r in rows]
