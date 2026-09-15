from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib
import uuid
from .core.models import Signal
from .core.adapters import QuerySignalAdapter, AlertSignalAdapter, InvestigationSignalAdapter
from .core.normalizer import normalize_entities
from .storage import SituationStore

RULE_VERSION="1.2"  # bumped for P0.1 + P0.2

def overlap_score(a: Signal, b: Signal) -> tuple[float, dict[str,list[str]]]:
    """Deterministic entity-overlap scorer with canonical normalization.

    P0.1 — query_id is now emitted by QuerySignalAdapter, so it can match
            the query_id entity emitted by InvestigationSignalAdapter.
    P0.2 — server / server_sk / server_name / scope_key are canonicalized
            to a single "server" key before scoring.
    """
    matched={}; score_num=0.0; score_den=0.0
    # Canonical weights (server_sk removed because it is now canonicalized to "server")
    weights={"query_id":1.0,"server":1.0,"bank":1.0,"metric":0.9,"kpi_name":0.9,"device_category":0.5}
    a_norm = normalize_entities(a.entities)
    b_norm = normalize_entities(b.entities)
    keys = set(a_norm) | set(b_norm)
    for key in keys:
        av = a_norm.get(key, set())
        bv = b_norm.get(key, set())
        if not av or not bv:
            continue
        w = weights.get(key, 0.25)
        score_den += w
        inter = av & bv
        if inter:
            score_num += w
            matched[key] = sorted(inter)
    return (score_num / score_den if score_den else 0.0), matched

def temporal_score(a: Signal,b: Signal,window_seconds:int)->float:
    d=abs((a.observed_at-b.observed_at).total_seconds())
    if d>window_seconds: return 0.0
    return 1.0-(d/window_seconds)

class SituationCorrelator:
    def __init__(self, store: SituationStore, memory_db: str="data/memory.db", alerts_db: str="data/agent_alerts.db", state_db: str="data/agent_state.db", window_seconds: int=900, threshold: float=0.60, weak_threshold: float=0.40):
        self.store=store; self.window_seconds=window_seconds; self.threshold=threshold; self.weak_threshold=weak_threshold
        self.state_db_path = state_db
        self.adapters=[QuerySignalAdapter(memory_db), AlertSignalAdapter(alerts_db), InvestigationSignalAdapter(state_db)]

    def collect(self, since: datetime, limit: int=1000)->list[Signal]:
        signals=[]
        for adapter in self.adapters: signals.extend(adapter.recent(since, limit))
        return sorted(signals,key=lambda s:s.observed_at)

    def _candidate_scores(self, signal:Signal):
        results=[]
        for row in self.store.find_candidate(signal.observed_at, signal.entities, self.window_seconds):
            import json
            entities=json.loads(row[1] or "{}")
            observed=datetime.fromisoformat(row[3])
            proxy=Signal("situation", "situation", observed, "sml", "", entities=entities)
            e_score, matched=overlap_score(signal,proxy)
            t=temporal_score(signal,proxy,self.window_seconds)
            score=0.7*e_score+0.3*t
            results.append((score,row[0],matched))
        return sorted(results,key=lambda x:x[0],reverse=True)

    def _link_investigation_trace(self, situation_id: str, signal: Signal) -> None:
        if signal.signal_type != "investigation":
            return
        investigation_id = signal.signal_id
        import sqlite3
        with sqlite3.connect(self.state_db_path) as conn:
            conn.row_factory = sqlite3.Row
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if "agent_runs" not in tables or "agent_iterations" not in tables:
                return
            rows = conn.execute("""
                SELECT r.id AS run_id, r.trace_id, COUNT(i.iteration_id) AS iteration_count
                FROM agent_runs r
                JOIN agent_iterations i ON i.run_id = r.id
                WHERE i.investigation_id = ?
                GROUP BY r.id, r.trace_id
                ORDER BY r.started_at
            """, (investigation_id,)).fetchall()
        for row in rows:
            self.store.link_loop_trace(situation_id, investigation_id, row["run_id"], row["trace_id"], row["iteration_count"])

    def _new_id(self, signal:Signal)->str:
        raw=f"{signal.source_system}:{signal.signal_type}:{signal.signal_id}"; digest=hashlib.sha1(raw.encode()).hexdigest()[:12]
        return f"SIT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{digest}"

    def run_once(self, lookback_minutes:int=30, limit:int=1000)->dict:
        started=datetime.now(timezone.utc); run_id=str(uuid.uuid4())
        signals=self.collect(started-timedelta(minutes=lookback_minutes),limit)
        unique={(s.source_system,s.signal_type,s.signal_id):s for s in signals}; signals=list(unique.values())
        matches=0; errors=0; created=0; weak_edges=0
        for signal in signals:
            try:
                candidates=self._candidate_scores(signal)
                candidate=candidates[0] if candidates else None
                if candidate and candidate[0] >= self.threshold:
                    score,sid,_=candidate
                    self.store.attach_signal(sid,signal,score); matches+=1
                    self._link_investigation_trace(sid, signal)
                else:
                    sid=self._new_id(signal)
                    self.store.create_situation(sid,signal,signal.entities,candidate[0] if candidate else 0.0,status="open")
                    self._link_investigation_trace(sid, signal)
                    created += 1
                    for score,other_sid,_ in candidates:
                        if score >= self.weak_threshold and score < self.threshold:
                            self.store.add_edge(sid, other_sid, "temporal_proximity", score)
                            weak_edges += 1
            except Exception:
                errors+=1
        finished=datetime.now(timezone.utc)
        self.store.save_correlation_run(run_id, started.isoformat(), finished.isoformat(), RULE_VERSION, len(signals), matches, errors)
        return {"run_id":run_id,"signals_seen":len(signals),"matches":matches,"created":created,"weak_edges":weak_edges,"errors":errors,"rule_version":RULE_VERSION,"started_at":started.isoformat(),"finished_at":finished.isoformat()}
