from __future__ import annotations
import json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

_ALLOWED_STATUSES = ("open", "correlated", "resolved", "false_positive", "escalated", "stale")
_ALLOWED_OUTCOMES = ("resolved", "worsened", "no_change", "escalated")

class SituationStore:
    def __init__(self, db_path: str = "data/situation_memory.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as c:
            c.executescript(f"""
            CREATE TABLE IF NOT EXISTS situations (
                situation_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                closed_at TEXT,
                status TEXT NOT NULL CHECK(status IN ('open','correlated','resolved','false_positive','escalated','stale')),
                entities_json TEXT NOT NULL,
                narrative TEXT,
                first_signal_at TEXT NOT NULL,
                last_signal_at TEXT NOT NULL,
                signal_count INTEGER NOT NULL DEFAULT 0,
                correlation_confidence REAL,
                pattern_family_id TEXT,
                pattern_drift_score REAL,
                resolution_action TEXT,
                resolution_outcome TEXT CHECK(resolution_outcome IN ('resolved','worsened','no_change','escalated')),
                resolution_time_minutes INTEGER,
                immutable_snapshot INTEGER NOT NULL DEFAULT 1,
                evidence_hash TEXT
            );
            CREATE TABLE IF NOT EXISTS situation_signals (
                situation_id TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                signal_id TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                correlation_score REAL,
                source_system TEXT NOT NULL,
                source_reference TEXT NOT NULL,
                attributes_json TEXT NOT NULL DEFAULT '{{}}',
                entities_json TEXT NOT NULL DEFAULT '{{}}',
                provenance_json TEXT NOT NULL DEFAULT '{{}}',
                PRIMARY KEY (situation_id, signal_type, signal_id)
            );
            CREATE TABLE IF NOT EXISTS situation_edges (
                edge_id TEXT PRIMARY KEY,
                from_situation_id TEXT NOT NULL,
                to_situation_id TEXT NOT NULL,
                edge_type TEXT NOT NULL CHECK(edge_type IN ('same_pattern','same_family','temporal_proximity','related')),
                confidence REAL,
                created_at TEXT NOT NULL,
                UNIQUE(from_situation_id, to_situation_id, edge_type)
            );
            CREATE TABLE IF NOT EXISTS situation_events (
                event_id TEXT PRIMARY KEY,
                situation_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{{}}'
            );
            CREATE TABLE IF NOT EXISTS correlation_runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                rule_version TEXT NOT NULL,
                signals_seen INTEGER NOT NULL DEFAULT 0,
                matches INTEGER NOT NULL DEFAULT 0,
                errors INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS situation_loop_refs (
                situation_id TEXT NOT NULL,
                investigation_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                trace_id TEXT,
                iteration_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                PRIMARY KEY (situation_id, run_id)
            );
            CREATE INDEX IF NOT EXISTS idx_situation_loop_refs_investigation
                ON situation_loop_refs(investigation_id);
            CREATE TABLE IF NOT EXISTS pattern_families (
                family_id TEXT PRIMARY KEY,
                signature_json TEXT NOT NULL,
                stage TEXT NOT NULL CHECK(stage IN ('CANDIDATE','SHADOW','VALIDATED','ACTIVE','DEPRECATED','REVOKED')),
                total_occurrences INTEGER NOT NULL DEFAULT 0,
                successful_resolutions INTEGER NOT NULL DEFAULT 0,
                success_rate REAL NOT NULL DEFAULT 0,
                wilson_lower_bound REAL NOT NULL DEFAULT 0,
                first_seen TEXT,
                last_seen TEXT,
                avg_resolution_time_minutes REAL,
                validated_at TEXT,
                activated_at TEXT,
                deprecated_at TEXT,
                revoked_at TEXT,
                status_reason TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_situations_time ON situations(first_signal_at, last_signal_at);
            CREATE INDEX IF NOT EXISTS idx_situations_status ON situations(status);
            CREATE INDEX IF NOT EXISTS idx_signals_lookup ON situation_signals(signal_type, signal_id);
            CREATE INDEX IF NOT EXISTS idx_signals_time ON situation_signals(observed_at);
            CREATE INDEX IF NOT EXISTS idx_events_situation ON situation_events(situation_id, occurred_at);
            CREATE INDEX IF NOT EXISTS idx_families_stage ON pattern_families(stage);
            """)
            # Upgrade databases created by older SML revisions without breaking them.
            cols={r[1] for r in c.execute("PRAGMA table_info(situation_signals)").fetchall()}
            for name, default in (("attributes_json", "'{}'"), ("entities_json", "'{}'"), ("provenance_json", "'{}'")):
                if name not in cols:
                    c.execute(f"ALTER TABLE situation_signals ADD COLUMN {name} TEXT NOT NULL DEFAULT {default}")

    def _event(self, situation_id: str, event_type: str, actor: str, payload: dict | None = None):
        with sqlite3.connect(self.db_path) as c:
            c.execute("INSERT INTO situation_events VALUES(?,?,?,?,?,?)", (
                uuid.uuid4().hex, situation_id, event_type, actor, datetime.now(timezone.utc).isoformat(), json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
            ))

    def create_situation(self, situation_id: str, signal, entities: dict[str,list[str]], confidence: float, status: str = "open", narrative: str = ""):
        if status not in _ALLOWED_STATUSES:
            raise ValueError(f"Invalid situation status: {status}")
        with sqlite3.connect(self.db_path) as c:
            ts=signal.observed_at.isoformat()
            c.execute("INSERT INTO situations(situation_id,created_at,status,entities_json,narrative,first_signal_at,last_signal_at,signal_count,correlation_confidence) VALUES(?,?,?,?,?,?,?,?,?)",
                      (situation_id, datetime.now(timezone.utc).isoformat(), status, json.dumps(entities, ensure_ascii=False, sort_keys=True), narrative, ts, ts, 0, confidence))
        self.attach_signal(situation_id, signal, confidence, actor="correlator")
        self._event(situation_id, "OPENED", "correlator", {"signal_id": signal.signal_id})

    def attach_signal(self, situation_id: str, signal, score: float | None = None, actor: str = "correlator"):
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            existing=c.execute("SELECT status, entities_json, first_signal_at, last_signal_at FROM situations WHERE situation_id=?",(situation_id,)).fetchone()
            if not existing:
                raise ValueError(f"Situation not found: {situation_id}")
            c.execute("INSERT OR IGNORE INTO situation_signals(situation_id,signal_type,signal_id,observed_at,correlation_score,source_system,source_reference,attributes_json,entities_json,provenance_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (situation_id, signal.signal_type, signal.signal_id, signal.observed_at.isoformat(), score, signal.source_system, signal.source_reference, json.dumps(signal.attributes or {}, ensure_ascii=False, sort_keys=True, default=str), json.dumps(signal.entities or {}, ensure_ascii=False, sort_keys=True), json.dumps(signal.provenance or {}, ensure_ascii=False, sort_keys=True, default=str)))
            entities=json.loads(existing["entities_json"] or "{}")
            for k, vals in signal.entities.items():
                bucket=entities.setdefault(k, [])
                for v in vals:
                    sv=str(v)
                    if sv not in bucket: bucket.append(sv)
            first=min(existing["first_signal_at"], signal.observed_at.isoformat())
            last=max(existing["last_signal_at"], signal.observed_at.isoformat())
            count=c.execute("SELECT COUNT(*) FROM situation_signals WHERE situation_id=?",(situation_id,)).fetchone()[0]
            current_conf=existing["status"] and c.execute("SELECT correlation_confidence FROM situations WHERE situation_id=?",(situation_id,)).fetchone()[0]
            new_conf=max(float(current_conf or 0.0), float(score or 0.0))
            new_status="correlated" if count >= 2 and existing["status"] == "open" else existing["status"]
            c.execute("UPDATE situations SET entities_json=?, first_signal_at=?, last_signal_at=?, signal_count=?, correlation_confidence=?, status=? WHERE situation_id=?",
                      (json.dumps(entities, ensure_ascii=False, sort_keys=True), first, last, count, new_conf, new_status, situation_id))
        self._event(situation_id, "SIGNAL_ATTACHED", actor, {"signal_id": signal.signal_id, "score": score})
        if new_status == "correlated" and existing["status"] != "correlated":
            self._event(situation_id, "CORRELATED", actor, {"signal_count": count})

    def find_candidate(self, observed_at: datetime, entities: dict[str,list[str]], window_seconds: int = 900, limit: int = 100):
        since=observed_at.timestamp()-window_seconds; until=observed_at.timestamp()+window_seconds
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            rows=c.execute("SELECT situation_id, entities_json, first_signal_at, last_signal_at, correlation_confidence FROM situations WHERE status IN ('open','correlated') ORDER BY last_signal_at DESC LIMIT ?",(limit,)).fetchall()
        candidates=[]
        for row in rows:
            try: ts=datetime.fromisoformat(row["last_signal_at"]).timestamp()
            except Exception: continue
            if since <= ts <= until: candidates.append(tuple(row))
        return candidates

    def get_situation(self, situation_id: str):
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            s=c.execute("SELECT * FROM situations WHERE situation_id=?",(situation_id,)).fetchone()
            if not s: return None
            sigs=c.execute("SELECT * FROM situation_signals WHERE situation_id=? ORDER BY observed_at",(situation_id,)).fetchall()
            events=c.execute("SELECT * FROM situation_events WHERE situation_id=? ORDER BY occurred_at",(situation_id,)).fetchall()
            return {"situation":dict(s), "signals":[dict(x) for x in sigs], "events":[dict(x) for x in events]}


    # Backwards-compatible aliases used by the hard-gate verification suite.
    def init_schema(self):
        self.init_db()

    def list_situations(self, limit=500):
        with sqlite3.connect(self.db_path) as c:
            return c.execute("SELECT * FROM situations ORDER BY last_signal_at DESC LIMIT ?", (limit,)).fetchall()

    def signals_for_situation(self, situation_id: str):
        with sqlite3.connect(self.db_path) as c:
            return c.execute("SELECT situation_id, signal_type, signal_id, source_system, observed_at, correlation_score FROM situation_signals WHERE situation_id=? ORDER BY observed_at", (situation_id,)).fetchall()

    def save_correlation_run(self, run_id: str, started_at: str, finished_at: str, rule_version: str, signals_seen: int, matches: int, errors: int):
        with sqlite3.connect(self.db_path) as c:
            c.execute("INSERT OR REPLACE INTO correlation_runs VALUES(?,?,?,?,?,?,?)", (run_id, started_at, finished_at, rule_version, signals_seen, matches, errors))

    def link_loop_trace(self, situation_id: str, investigation_id: str, run_id: str, trace_id: str | None, iteration_count: int) -> None:
        with sqlite3.connect(self.db_path) as c:
            c.execute("INSERT OR REPLACE INTO situation_loop_refs(situation_id, investigation_id, run_id, trace_id, iteration_count, created_at) VALUES(?,?,?,?,?,?)",
                      (situation_id, investigation_id, run_id, trace_id, int(iteration_count), datetime.now(timezone.utc).isoformat()))

    def get_loop_refs(self, situation_id: str) -> list[dict]:
        with sqlite3.connect(self.db_path) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute("SELECT situation_id, investigation_id, run_id, trace_id, iteration_count, created_at FROM situation_loop_refs WHERE situation_id=? ORDER BY created_at", (situation_id,)).fetchall()
            return [dict(r) for r in rows]

    def recent_situations(self, limit=500):
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            return [dict(x) for x in c.execute("SELECT * FROM situations ORDER BY last_signal_at DESC LIMIT ?",(limit,)).fetchall()]

    def add_edge(self, from_situation_id: str, to_situation_id: str, edge_type: str, confidence: float):
        if from_situation_id == to_situation_id: return
        with sqlite3.connect(self.db_path) as c:
            c.execute("INSERT OR IGNORE INTO situation_edges(edge_id,from_situation_id,to_situation_id,edge_type,confidence,created_at) VALUES(?,?,?,?,?,?)", (uuid.uuid4().hex, from_situation_id, to_situation_id, edge_type, float(confidence), datetime.now(timezone.utc).isoformat()))

    def add_family_edges(self, family_id: str, latest_situation_id: str, confidence: float = 0.7, limit: int = 20):
        with sqlite3.connect(self.db_path) as c:
            ids=[r[0] for r in c.execute("SELECT situation_id FROM situations WHERE pattern_family_id=? AND situation_id<>? ORDER BY last_signal_at DESC LIMIT ?",(family_id,latest_situation_id,limit)).fetchall()]
        for sid in ids:
            self.add_edge(latest_situation_id, sid, "same_family", confidence)

    def upsert_pattern_family(self, family: dict):
        with sqlite3.connect(self.db_path) as c:
            c.execute("""INSERT INTO pattern_families(family_id,signature_json,stage,total_occurrences,successful_resolutions,success_rate,wilson_lower_bound,first_seen,last_seen,avg_resolution_time_minutes,validated_at,activated_at,deprecated_at,revoked_at,status_reason,updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(family_id) DO UPDATE SET signature_json=excluded.signature_json,total_occurrences=excluded.total_occurrences,successful_resolutions=excluded.successful_resolutions,success_rate=excluded.success_rate,wilson_lower_bound=excluded.wilson_lower_bound,first_seen=excluded.first_seen,last_seen=excluded.last_seen,avg_resolution_time_minutes=excluded.avg_resolution_time_minutes,stage=CASE WHEN pattern_families.stage IN ('VALIDATED','ACTIVE','DEPRECATED','REVOKED') THEN pattern_families.stage ELSE excluded.stage END,updated_at=excluded.updated_at,status_reason=excluded.status_reason""", (
                family["family_id"], json.dumps(family["signature"], ensure_ascii=False, sort_keys=True), family["stage"], family["total_occurrences"], family["successful_resolutions"], family["success_rate"], family["wilson_lower_bound"], family.get("first_seen"), family.get("last_seen"), family.get("avg_resolution_time_minutes"), family.get("validated_at"), family.get("activated_at"), family.get("deprecated_at"), family.get("revoked_at"), family.get("status_reason"), datetime.now(timezone.utc).isoformat()))

    def get_pattern_family(self, family_id: str):
        with sqlite3.connect(self.db_path) as c:
            c.row_factory=sqlite3.Row
            row=c.execute("SELECT * FROM pattern_families WHERE family_id=?",(family_id,)).fetchone()
            return dict(row) if row else None

    def transition_family(self, family_id: str, stage: str, actor: str, reason: str = ""):
        if stage not in ("VALIDATED","ACTIVE","DEPRECATED","REVOKED"): raise ValueError("Invalid family transition")
        now=datetime.now(timezone.utc)
        with sqlite3.connect(self.db_path) as c:
            row=c.execute("SELECT stage,validated_at,success_rate,wilson_lower_bound,last_seen FROM pattern_families WHERE family_id=?",(family_id,)).fetchone()
            if not row: raise ValueError(f"Pattern family not found: {family_id}")
            current, validated_at, success_rate, lb, last_seen=row
            if stage=="VALIDATED":
                if current not in ("SHADOW","CANDIDATE"): raise ValueError(f"Cannot validate family from {current}")
                c.execute("UPDATE pattern_families SET stage='VALIDATED', validated_at=?, status_reason=?, updated_at=? WHERE family_id=?",(now.isoformat(),reason,now.isoformat(),family_id))
            elif stage=="ACTIVE":
                if current!="VALIDATED": raise ValueError("ACTIVE requires VALIDATED stage")
                if not validated_at: raise ValueError("validated_at missing")
                age=(now-datetime.fromisoformat(validated_at)).total_seconds()/86400
                if age < 7: raise ValueError(f"7-day validation period not met: {age:.2f} days")
                if float(success_rate or 0) < 0.80 or float(lb or 0) < 0.65: raise ValueError("Statistical activation thresholds not met")
                c.execute("UPDATE pattern_families SET stage='ACTIVE', activated_at=?, status_reason=?, updated_at=? WHERE family_id=?",(now.isoformat(),reason,now.isoformat(),family_id))
            else:
                c.execute("UPDATE pattern_families SET stage=?, deprecated_at=CASE WHEN ?='DEPRECATED' THEN ? ELSE deprecated_at END, revoked_at=CASE WHEN ?='REVOKED' THEN ? ELSE revoked_at END, status_reason=?, updated_at=? WHERE family_id=?",(stage,stage,now.isoformat(),stage,now.isoformat(),reason,now.isoformat(),family_id))
        return self.get_pattern_family(family_id)

    def close_situation(self, situation_id: str, outcome: str, action: str = "", resolved_at: datetime | None = None):
        if outcome not in _ALLOWED_OUTCOMES: raise ValueError(f"Invalid outcome: {outcome}")
        with sqlite3.connect(self.db_path) as c:
            row=c.execute("SELECT first_signal_at,status FROM situations WHERE situation_id=?",(situation_id,)).fetchone()
            if not row: raise ValueError(f"Situation not found: {situation_id}")
            if row[1] in ("resolved","false_positive","escalated","stale"): return
            resolved=resolved_at or datetime.now(timezone.utc)
            try: mins=max(0,int((resolved-datetime.fromisoformat(row[0])).total_seconds()/60))
            except Exception: mins=None
            status="resolved" if outcome=="resolved" else "false_positive" if outcome=="false_positive" else "escalated"
            c.execute("UPDATE situations SET status=?, closed_at=?, resolution_action=?, resolution_outcome=?, resolution_time_minutes=? WHERE situation_id=?",
                      (status, resolved.isoformat(), action, outcome, mins, situation_id))
        self._event(situation_id, "RESOLUTION_RECORDED", "human", {"outcome":outcome,"action":action})
