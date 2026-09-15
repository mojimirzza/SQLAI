"""
State Manager — The sidecar's own SQLite database.
Stores agent outputs, suggestion history, investigation records.
NEVER writes to memory.db or warehouse.db.
"""
from __future__ import annotations
import sqlite3
import json
import os
from datetime import datetime
from typing import Any


class StateManager:
    """Agent state persistence. Separate from main project databases."""

    def __init__(self, db_path: str = "data/agent_state.db"):
        self.db_path = db_path
        parent = os.path.dirname(os.path.abspath(self.db_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Investigations
            conn.execute("""
                CREATE TABLE IF NOT EXISTS investigations (
                    id TEXT PRIMARY KEY,
                    query_id TEXT NOT NULL,
                    triggered_at TEXT NOT NULL,
                    hypothesis TEXT,
                    confidence TEXT,
                    drilldown_count INTEGER DEFAULT 0,
                    report_path TEXT,
                    status TEXT DEFAULT 'open',
                    resolved_at TEXT
                )
            """)
            # Follow-up suggestions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS followup_suggestions (
                    id TEXT PRIMARY KEY,
                    query_id TEXT NOT NULL,
                    session_id TEXT,
                    suggestions_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    user_clicked INTEGER DEFAULT 0
                )
            """)
            # Gap reports
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gap_reports (
                    id TEXT PRIMARY KEY,
                    report_date TEXT NOT NULL,
                    report_path TEXT NOT NULL,
                    missing_metrics_json TEXT,
                    missing_dimensions_json TEXT,
                    generated_at TEXT NOT NULL
                )
            """)
            # Agent runs log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    success INTEGER DEFAULT 0,
                    output_summary TEXT,
                    trace_id TEXT
                )
            """)
            # Alert correlation tracking
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_correlations (
                    id TEXT PRIMARY KEY,
                    investigation_id TEXT,
                    alert_id TEXT,
                    metric_name TEXT,
                    correlation_type TEXT,  -- triggered_by | similar_pattern | root_cause_match
                    confidence REAL,
                    created_at TEXT NOT NULL
                )
            """)
            # ReAct loop iterations — append-only execution trace.
            conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_iterations (
                    iteration_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    investigation_id TEXT,
                    iteration_no INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    decision_action TEXT NOT NULL,
                    decision_reason TEXT,
                    action_input_json TEXT NOT NULL,
                    observation_json TEXT,
                    action_status TEXT NOT NULL DEFAULT 'pending',
                    verification_status TEXT NOT NULL DEFAULT 'pending',
                    verification_reason TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    termination_reason TEXT,
                    UNIQUE(run_id, iteration_no)
                )
            """)
            # Backward-compatible schema hardening for existing sidecar DBs.
            existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(agent_iterations)").fetchall()}
            if "decision_reason" not in existing_cols:
                conn.execute("ALTER TABLE agent_iterations ADD COLUMN decision_reason TEXT")
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_iterations_run
                ON agent_iterations(run_id, iteration_no)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS loop_events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    investigation_id TEXT,
                    iteration_id TEXT,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_loop_events_run
                ON loop_events(run_id, created_at)
            """)
            conn.commit()

    def log_run(self, run_id: str, agent_name: str, mode: str,
                started_at: datetime, finished_at: datetime | None = None,
                success: bool = False, output_summary: str = "",
                trace_id: str = "") -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO agent_runs
                   (id, agent_name, mode, started_at, finished_at, success, output_summary, trace_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (run_id, agent_name, mode, started_at.isoformat(),
                 finished_at.isoformat() if finished_at else None,
                 1 if success else 0, output_summary, trace_id)
            )
            conn.commit()

    def save_investigation(self, investigation_id: str, query_id: str,
                           hypothesis: str, confidence: str,
                           drilldown_count: int, report_path: str) -> None:
        """Create or update an investigation record without losing its start time."""
        with sqlite3.connect(self.db_path) as conn:
            existing = conn.execute("SELECT id FROM investigations WHERE id = ?", (investigation_id,)).fetchone()
            if existing:
                conn.execute(
                    """UPDATE investigations
                       SET hypothesis = ?, confidence = ?, drilldown_count = ?, report_path = ?,
                           status = ?, resolved_at = CASE WHEN ? THEN ? ELSE resolved_at END
                       WHERE id = ?""",
                    (hypothesis, confidence, drilldown_count, report_path,
                     "resolved" if report_path else "open",
                     bool(report_path), datetime.now().isoformat() if report_path else None,
                     investigation_id)
                )
            else:
                conn.execute(
                    """INSERT INTO investigations
                       (id, query_id, triggered_at, hypothesis, confidence, drilldown_count, report_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (investigation_id, query_id, datetime.now().isoformat(),
                     hypothesis, confidence, drilldown_count, report_path)
                )
            conn.commit()

    def save_suggestions(self, suggestion_id: str, query_id: str,
                         session_id: str, suggestions: list[str]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO followup_suggestions
                   (id, query_id, session_id, suggestions_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (suggestion_id, query_id, session_id,
                 json.dumps(suggestions, ensure_ascii=False),
                 datetime.now().isoformat())
            )
            conn.commit()

    def save_gap_report(self, report_id: str, report_date: str,
                        report_path: str, missing_metrics: list[str],
                        missing_dimensions: list[str]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO gap_reports
                   (id, report_date, report_path, missing_metrics_json, missing_dimensions_json, generated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (report_id, report_date, report_path,
                 json.dumps(missing_metrics, ensure_ascii=False),
                 json.dumps(missing_dimensions, ensure_ascii=False),
                 datetime.now().isoformat())
            )
            conn.commit()

    def start_iteration(self, run_id: str, iteration_id: str, iteration_no: int,
                        decision_action: str, action_input: dict,
                        decision_reason: str = "",
                        investigation_id: str | None = None,
                        started_at: datetime | None = None) -> None:
        started_at = started_at or datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO agent_iterations
                   (iteration_id, run_id, investigation_id, iteration_no, started_at,
                    decision_action, decision_reason, action_input_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (iteration_id, run_id, investigation_id, iteration_no, started_at.isoformat(),
                 decision_action, decision_reason, json.dumps(action_input, ensure_ascii=False, default=str))
            )
            conn.execute(
                """INSERT INTO loop_events
                   (id, run_id, investigation_id, iteration_id, event_type, created_at, payload_json)
                   VALUES (?, ?, ?, ?, 'decision', ?, ?)""",
                (str(__import__('uuid').uuid4()), run_id, investigation_id, iteration_id,
                 started_at.isoformat(), json.dumps({
                     "action": decision_action, "decision_reason": decision_reason, "action_input": action_input, "iteration_no": iteration_no
                 }, ensure_ascii=False, default=str))
            )
            conn.commit()

    def finish_iteration(self, iteration_id: str, observation: Any, action_status: str,
                         verification_status: str, verification_reason: str,
                         retry_count: int = 0, termination_reason: str | None = None,
                         finished_at: datetime | None = None) -> None:
        finished_at = finished_at or datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT run_id, investigation_id, iteration_no FROM agent_iterations WHERE iteration_id = ?", (iteration_id,)).fetchone()
            if not row:
                raise KeyError(f"Unknown iteration_id: {iteration_id}")
            run_id, investigation_id, iteration_no = row
            conn.execute(
                """UPDATE agent_iterations
                   SET finished_at = ?, observation_json = ?, action_status = ?,
                       verification_status = ?, verification_reason = ?, retry_count = ?,
                       termination_reason = ?
                   WHERE iteration_id = ?""",
                (finished_at.isoformat(), json.dumps(observation, ensure_ascii=False, default=str),
                 action_status, verification_status, verification_reason, retry_count,
                 termination_reason, iteration_id)
            )
            conn.execute(
                """INSERT INTO loop_events
                   (id, run_id, investigation_id, iteration_id, event_type, created_at, payload_json)
                   VALUES (?, ?, ?, ?, 'observation', ?, ?)""",
                (str(__import__('uuid').uuid4()), run_id, investigation_id, iteration_id,
                 finished_at.isoformat(), json.dumps({
                     "iteration_no": iteration_no, "action_status": action_status,
                     "verification_status": verification_status,
                     "verification_reason": verification_reason,
                     "retry_count": retry_count, "termination_reason": termination_reason,
                     "observation": observation
                 }, ensure_ascii=False, default=str))
            )
            conn.commit()

    def terminate_iteration(self, iteration_id: str, termination_reason: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE agent_iterations SET termination_reason = ? WHERE iteration_id = ?",
                (termination_reason, iteration_id),
            )
            conn.commit()

    def get_run_iterations(self, run_id: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM agent_iterations WHERE run_id = ? ORDER BY iteration_no", (run_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_loop_events(self, run_id: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM loop_events WHERE run_id = ? ORDER BY created_at", (run_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_suggestions_for_session(self, session_id: str, limit: int = 10) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM followup_suggestions WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
                (session_id, limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def save_alert_correlation(self, correlation_id: str, investigation_id: str,
                                alert_id: str, metric_name: str,
                                correlation_type: str, confidence: float) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO alert_correlations
                   (id, investigation_id, alert_id, metric_name, correlation_type, confidence, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (correlation_id, investigation_id, alert_id, metric_name,
                 correlation_type, confidence, datetime.now().isoformat())
            )
            conn.commit()

    def update_investigation_status(self, investigation_id: str, status: str,
                                   resolved_at: datetime | None = None) -> None:
        allowed = {"open", "resolved", "false_positive", "escalated"}
        if status not in allowed:
            raise ValueError(f"invalid investigation status: {status}")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE investigations SET status = ?, resolved_at = ? WHERE id = ?",
                (status, resolved_at.isoformat() if resolved_at else None, investigation_id),
            )
            conn.commit()

    def get_alert_correlations(self, investigation_id: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM alert_correlations WHERE investigation_id = ? ORDER BY created_at DESC",
                (investigation_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_open_investigations(self, limit: int = 20) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM investigations WHERE status = 'open' ORDER BY triggered_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
