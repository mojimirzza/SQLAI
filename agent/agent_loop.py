import os
"""
Agent Loop
Simple ReAct pattern: observe → decide → act → log
"""
import sqlite3
from datetime import datetime

from agent.tools.query_baseline import query_baseline
from agent.tools.check_maintenance import check_maintenance_window
from agent.tools.send_alert import send_alert
from agent.objective_definer import define_objective


def run_agent_cycle(db_path: str = "data/bank.duckdb", slack_webhook: str | None = None):
    """
    One full agent cycle:
    1. Observe: query unalerted anomalies
    2. Decide: define objective for each
    3. Act: send alert or suppress
    4. Log: record decision for future learning
    """
    print(f"\n[{datetime.now().isoformat()}] Agent cycle started")

    # Step 1: Observe
    anomalies = query_baseline(db_path)
    print(f"  Found {len(anomalies)} unalerted anomalies")

    if not anomalies:
        print("  Nothing to do.")
        return

    # Warehouse DB for reading baselines and updating alerted flag
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB is required for the alert agent warehouse connection") from exc
    wh_conn = duckdb.connect(db_path)

    # Agent alerts DB for writing alert logs (separate to avoid contention)
    alert_db_path = os.environ.get("AGENT_ALERT_DB", "data/agent_alerts.db")
    os.makedirs(os.path.dirname(alert_db_path), exist_ok=True)
    alert_conn = sqlite3.connect(alert_db_path)
    alert_conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_log (
            alert_id TEXT PRIMARY KEY,
            triggered_at TEXT NOT NULL,
            metric_name TEXT,
            server_sk INTEGER,
            severity TEXT,
            message TEXT,
            decision_reasoning TEXT,
            action_taken TEXT,
            sent_successfully INTEGER,
            acknowledged_at TEXT,
            resolved_at TEXT,
            was_real_incident INTEGER,
            false_positive INTEGER
        )
    """)
    alert_conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_alert_time ON alert_log(triggered_at DESC)
    """)
    alert_conn.commit()

    for anomaly in anomalies:
        metric = anomaly.get("metric_name", "unknown")
        server = anomaly.get("server_sk")

        print(f"\n  Processing: {metric} (server={server})")

        # Step 2: Decide
        in_maintenance = check_maintenance_window(server)
        objective = define_objective(anomaly, in_maintenance)

        print(f"    Decision: {objective.action} | Severity: {objective.severity}")
        print(f"    Reasoning: {objective.reasoning}")

        # Step 3: Act
        if objective.action == "alert":
            result = send_alert(anomaly, objective.severity, objective.channel, slack_webhook)
            print(f"    Alert sent: {result['sent']} → {result['channel']}")

            # Mark as alerted
            wh_conn.execute("""
                UPDATE metric_daily_baseline 
                SET alerted = 1 
                WHERE baseline_date = ? AND metric_name = ? 
                  AND COALESCE(server_sk, -1) = COALESCE(?, -1)
                  AND COALESCE(device_category, 'NULL') = COALESCE(?, 'NULL')
                  AND COALESCE(hour24, -1) = COALESCE(?, -1)
            """, (
                anomaly["baseline_date"], anomaly["metric_name"],
                anomaly.get("server_sk"), anomaly.get("device_category"),
                anomaly.get("hour24")
            ))

            # Log
            alert_conn.execute("""
                INSERT INTO alert_log 
                (alert_id, triggered_at, metric_name, server_sk, severity, 
                 message, decision_reasoning, action_taken, sent_successfully)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{metric}_{server or 'all'}",
                datetime.now().isoformat(),
                metric,
                server,
                objective.severity,
                result["message"],
                objective.reasoning,
                objective.action,
                result["sent"]
            ))

        elif objective.action == "suppress":
            print(f"    Suppressed: {objective.suppress_reason}")

            # Mark as alerted (so we don't re-check)
            wh_conn.execute("""
                UPDATE metric_daily_baseline 
                SET alerted = 1 
                WHERE baseline_date = ? AND metric_name = ?
                  AND COALESCE(server_sk, -1) = COALESCE(?, -1)
            """, (anomaly["baseline_date"], metric, server))

            # Log suppression
            alert_conn.execute("""
                INSERT INTO alert_log 
                (alert_id, triggered_at, metric_name, server_sk, severity,
                 message, decision_reasoning, action_taken, sent_successfully)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{metric}_{server or 'all'}",
                datetime.now().isoformat(),
                metric,
                server,
                "suppressed",
                f"Suppressed: {objective.suppress_reason}",
                objective.reasoning,
                "suppress",
                False
            ))

        else:  # log_only
            print(f"    Logged only (no alert)")
            # Don't mark alerted — we might want to alert later if it worsens

    wh_conn.commit()
    wh_conn.close()
    alert_conn.commit()
    alert_conn.close()

    print(f"\n[{datetime.now().isoformat()}] Agent cycle complete")
