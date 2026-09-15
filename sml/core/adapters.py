from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from .models import Signal
from .normalizer import normalize_entities, register_server_mapping


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if x not in (None, "")]
    return [str(value)]


def _safe_json(value, default):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


class QuerySignalAdapter:
    source_system = "src"
    signal_type = "query"
    def __init__(self, db_path: str):
        self.db_path = db_path
    def recent(self, since: datetime, limit: int = 500) -> list[Signal]:
        if not Path(self.db_path).exists(): return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM query_records WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT ?", (since.isoformat(), limit)).fetchall()
        out=[]
        for r in rows:
            entities = _safe_json(r["intent_entities"], {}) or {}
            norm={k:_as_list(v) for k,v in entities.items()}
            # P0.1 — expose the query record's own ID as a query_id entity
            norm["query_id"] = [str(r["id"])]
            if r["sql_metric"]: norm.setdefault("metric", []).append(str(r["sql_metric"]))
            # P0.2 — canonicalize server-related keys without mutating a list
            # while iterating over it (the previous implementation could loop forever).
            server_values = []
            for srv_key in ("server", "server_name", "server_sk", "scope_key"):
                server_values.extend(norm.get(srv_key, []))
            if server_values:
                norm["server"] = list(dict.fromkeys(str(v) for v in server_values))
            out.append(Signal(
                signal_id=str(r["id"]), signal_type=self.signal_type,
                observed_at=datetime.fromisoformat(r["timestamp"]), source_system=self.source_system,
                source_reference=f"{self.db_path}:query_records:{r['id']}", entities=norm,
                attributes={"query_text": r["query_text"], "intent_category": r["intent_category"], "confidence": r["confidence"], "execution_success": bool(r["execution_success"])},
                provenance={"db": self.db_path, "table": "query_records"},
            ))
        return out


class AlertSignalAdapter:
    source_system = "agents"
    signal_type = "alert"
    def __init__(self, db_path: str): self.db_path = db_path
    def recent(self, since: datetime, limit: int = 500) -> list[Signal]:
        if not Path(self.db_path).exists(): return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM alert_log WHERE triggered_at >= ? ORDER BY triggered_at ASC LIMIT ?", (since.isoformat(), limit)).fetchall()
        out=[]
        for r in rows:
            entities={"metric":[str(r["metric_name"])] if r["metric_name"] else [], "server_sk":[str(r["server_sk"])] if r["server_sk"] is not None else []}
            # P0.2 — also expose server_sk under canonical "server" key so it can
            # overlap with query intent_entities that carry server names.
            if r["server_sk"] is not None:
                entities.setdefault("server", []).append(str(r["server_sk"]))
            out.append(Signal(
                signal_id=str(r["alert_id"]), signal_type=self.signal_type,
                observed_at=datetime.fromisoformat(r["triggered_at"]), source_system=self.source_system,
                source_reference=f"{self.db_path}:alert_log:{r['alert_id']}", entities=entities,
                attributes={k:r[k] for k in ("severity","message","decision_reasoning","action_taken","was_real_incident","false_positive","resolved_at")},
                provenance={"db": self.db_path, "table": "alert_log"},
            ))
        return out


class InvestigationSignalAdapter:
    source_system = "sidecar"
    signal_type = "investigation"
    def __init__(self, db_path: str): self.db_path = db_path
    def recent(self, since: datetime, limit: int = 500) -> list[Signal]:
        if not Path(self.db_path).exists(): return []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM investigations WHERE triggered_at >= ? ORDER BY triggered_at ASC LIMIT ?", (since.isoformat(), limit)).fetchall()
        out=[]
        for r in rows:
            attrs={k:r[k] for k in ("query_id","hypothesis","confidence","drilldown_count","report_path","status","resolved_at")}
            entities={"query_id":[str(r["query_id"])] if r["query_id"] else []}
            # P0.2 — if investigation carries server info, canonicalize it
            # (future: read from a server_sk column if added to schema)
            if r["hypothesis"]: attrs["hypothesis"] = r["hypothesis"]
            out.append(Signal(
                signal_id=str(r["id"]), signal_type=self.signal_type,
                observed_at=datetime.fromisoformat(r["triggered_at"]), source_system=self.source_system,
                source_reference=f"{self.db_path}:investigations:{r['id']}", entities=entities,
                attributes=attrs, provenance={"db": self.db_path, "table": "investigations"},
            ))
        return out
