"""
DB Reader — Read-only access to main project's SQLite and DuckDB.
Zero writes to memory.db or warehouse.db. All writes go to agent_state.db.
"""
from __future__ import annotations
import sqlite3
import os
import json
from datetime import datetime, timedelta
from typing import Any

import duckdb
import yaml


class DBReader:
    """Unified read-only interface to all data sources."""

    def __init__(self, memory_db_path: str, warehouse_db_path: str,
                 semantic_layer_path: str, trace_logs_dir: str | None = None,
                 agent_alerts_db_path: str | None = None):
        self.memory_db_path = memory_db_path
        self.warehouse_db_path = warehouse_db_path
        self.semantic_layer_path = semantic_layer_path
        self.trace_logs_dir = trace_logs_dir
        self.agent_alerts_db_path = agent_alerts_db_path

    # ------------------------------------------------------------------
    # SQLite Memory (query history)
    # ------------------------------------------------------------------
    def get_recent_queries(self, days: int = 7, min_confidence: float | None = None,
                           limit: int = 500) -> list[dict]:
        """Fetch recent query records from memory.db."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.memory_db_path) as conn:
            conn.row_factory = sqlite3.Row
            sql = """
                SELECT * FROM query_records
                WHERE timestamp >= ?
                {conf_filter}
                ORDER BY timestamp DESC
                LIMIT ?
            """.format(
                conf_filter="AND confidence < ?" if min_confidence is not None else ""
            )
            params = [since]
            if min_confidence is not None:
                params.append(min_confidence)
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_query_by_id(self, query_id: str) -> dict | None:
        """Fetch a single query record by its UUID."""
        with sqlite3.connect(self.memory_db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM query_records WHERE id = ?", (query_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_session_queries(self, session_id: str, limit: int = 20) -> list[dict]:
        """Fetch queries from a specific session."""
        with sqlite3.connect(self.memory_db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM query_records WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_anomalous_queries(self, days: int = 7, min_severity: str = "medium") -> list[dict]:
        """Fetch queries where baseline flagged an anomaly.
        Note: anomaly data is in the JSON trace logs or can be inferred from
        the response_type / confidence patterns. For now, we look at queries
        with very low confidence or rejected status as proxy."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.memory_db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM query_records
                   WHERE timestamp >= ?
                     AND (confidence < 0.50 OR response_type = 'REJECTED' OR response_type = 'CLARIFICATION')
                   ORDER BY timestamp DESC""",
                (since,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # DuckDB Warehouse (transaction data)
    # ------------------------------------------------------------------
    def execute_warehouse(self, sql: str, readonly: bool = True) -> list[dict]:
        """Execute a read-only SQL query against DuckDB warehouse."""
        conn = duckdb.connect(self.warehouse_db_path, read_only=readonly)
        try:
            result = conn.execute(sql).fetchdf()
            return result.to_dict(orient="records")
        finally:
            conn.close()

    def get_table_schema(self, table_name: str) -> list[dict]:
        """Get column info for a warehouse table."""
        return self.execute_warehouse(
            f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table_name}'"
        )

    # ------------------------------------------------------------------
    # Semantic Layer (YAML)
    # ------------------------------------------------------------------
    def get_semantic_layer(self) -> dict:
        """Parse the semantic layer YAML."""
        with open(self.semantic_layer_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def list_metrics(self) -> list[str]:
        """List all defined metric names."""
        layer = self.get_semantic_layer()
        return list(layer.get("metrics", {}).keys())

    def list_dimensions(self) -> list[str]:
        """List all defined dimension names."""
        layer = self.get_semantic_layer()
        dims = []
        for table_name, table_def in layer.get("tables", {}).items():
            for col in table_def.get("columns", []):
                dims.append(col.get("name", ""))
        return dims


    # ------------------------------------------------------------------
    # Agent Alerts DB (read-only — alert agent's own database)
    # ------------------------------------------------------------------
    def get_alert_history(self, days: int = 7, metric_name: str | None = None) -> list[dict]:
        """Fetch alert history from the alert agent's database."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        import sqlite3
        # agent_alerts_db path is relative to the sidecar config
        alert_db = self._resolve_alert_db()
        if not alert_db or not os.path.exists(alert_db):
            return []
        with sqlite3.connect(alert_db) as conn:
            conn.row_factory = sqlite3.Row
            sql = """
                SELECT * FROM alert_log
                WHERE triggered_at >= ?
                {metric_filter}
                ORDER BY triggered_at DESC
            """.format(
                metric_filter="AND metric_name = ?" if metric_name else ""
            )
            params = [since]
            if metric_name:
                params.append(metric_name)
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_open_alerts(self) -> list[dict]:
        """Fetch alerts that have not been resolved or acknowledged."""
        import sqlite3
        alert_db = self._resolve_alert_db()
        if not alert_db or not os.path.exists(alert_db):
            return []
        with sqlite3.connect(alert_db) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM alert_log
                WHERE resolved_at IS NULL
                   OR (was_real_incident IS NULL AND false_positive IS NULL)
                ORDER BY triggered_at DESC
                LIMIT 50
            """).fetchall()
            return [dict(r) for r in rows]

    def _resolve_alert_db(self) -> str | None:
        """Resolve agent_alerts.db path from config or default."""
        if self.agent_alerts_db_path and os.path.exists(self.agent_alerts_db_path):
            return self.agent_alerts_db_path
        # Default relative to sidecar location
        default = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "agent_alerts.db")
        return os.path.abspath(default)

    # ------------------------------------------------------------------
    # Trace Logs (JSONL)
    # ------------------------------------------------------------------
    def read_trace_events(self, trace_id: str) -> list[dict]:
        """Read trace log events for a specific trace_id.
        Assumes JSONL format: one JSON object per line."""
        if not self.trace_logs_dir:
            return []
        import os
        import glob
        pattern = os.path.join(self.trace_logs_dir, f"*{trace_id}*.jsonl")
        files = glob.glob(pattern)
        events = []
        for filepath in files:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return events
