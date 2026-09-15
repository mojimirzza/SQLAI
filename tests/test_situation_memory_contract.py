from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sml.storage import SituationStore
from sml.correlator import SituationCorrelator
from sml.retrieval import SituationMemoryRetriever
from sml.core.contracts import SituationMemoryRequest


def _dbs(tmp_path: Path, when: datetime):
    mem, alerts, state, sit = [tmp_path / x for x in ("memory.db","alerts.db","state.db","situation.db")]
    with sqlite3.connect(mem) as c:
        c.execute("CREATE TABLE query_records (id TEXT PRIMARY KEY,user_id TEXT,session_id TEXT,query_text TEXT,timestamp TEXT,intent_category TEXT,intent_entities TEXT,generated_sql TEXT,sql_metric TEXT,sql_dimensions TEXT,sql_filters TEXT,sql_joins TEXT,execution_row_count INTEGER,execution_success INTEGER,response_type TEXT,confidence REAL)")
        for i,mins in (("q1",0),("q2",-120)):
            c.execute("INSERT INTO query_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (i,"u","s","latency Mellat",(when+timedelta(minutes=mins)).isoformat(),"latency",json.dumps({"server":["SRV-A"],"bank":["Mellat"],"metric":["avg_latency"]}),"SELECT 1","avg_latency","[]","[]","[]",1,1,"sql_only",.9))
    with sqlite3.connect(alerts) as c:
        c.execute("CREATE TABLE alert_log (alert_id TEXT PRIMARY KEY,triggered_at TEXT,metric_name TEXT,server_sk INTEGER,severity TEXT,message TEXT,decision_reasoning TEXT,action_taken TEXT,sent_successfully INTEGER,acknowledged_at TEXT,resolved_at TEXT,was_real_incident INTEGER,false_positive INTEGER)")
        c.execute("INSERT INTO alert_log VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", ("a1",when.isoformat(),"avg_latency",1,"high","spike","reason","alert",1,None,None,1,0))
    with sqlite3.connect(state) as c:
        c.execute("CREATE TABLE investigations (id TEXT PRIMARY KEY,query_id TEXT,triggered_at TEXT,hypothesis TEXT,confidence TEXT,drilldown_count INTEGER,report_path TEXT,status TEXT,resolved_at TEXT)")
        c.execute("INSERT INTO investigations VALUES (?,?,?,?,?,?,?,?,?)", ("i1","q1",when.isoformat(),"latency spike","high",2,"r.md","resolved",when.isoformat()))
        c.execute("CREATE TABLE agent_runs (id TEXT PRIMARY KEY,agent_name TEXT,mode TEXT,started_at TEXT,finished_at TEXT,success INTEGER,output_summary TEXT,trace_id TEXT)")
        c.execute("CREATE TABLE agent_iterations (iteration_id TEXT PRIMARY KEY,run_id TEXT,investigation_id TEXT,iteration_no INTEGER,started_at TEXT,finished_at TEXT,decision_action TEXT,decision_reason TEXT,action_input_json TEXT,observation_json TEXT,action_status TEXT,verification_status TEXT,verification_reason TEXT,retry_count INTEGER,termination_reason TEXT)")
        for n in (1,2):
            c.execute("INSERT INTO agent_iterations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (f"it{n}","r1","i1",n,when.isoformat(),when.isoformat(),"query_warehouse","because","{}","{}","ok","passed","ok",0,None))
        c.execute("INSERT INTO agent_runs VALUES (?,?,?,?,?,?,?,?)", ("r1","react","investigate",when.isoformat(),when.isoformat(),1,"done","tr1"))
    return mem, alerts, state, sit


def test_retrieval_returns_context_only_and_links_loop(tmp_path):
    now=datetime.now(timezone.utc).replace(microsecond=0)
    mem, alerts, state, sit = _dbs(tmp_path, now)
    store=SituationStore(str(sit))
    SituationCorrelator(store, str(mem), str(alerts), str(state)).run_once(lookback_minutes=10)
    # historical retrieval should find a situation matching the same bank/server/metric.
    response=SituationMemoryRetriever(store).retrieve(SituationMemoryRequest(entities={"bank":["Mellat"],"server":["SRV-A"],"metric":["avg_latency"]}, min_score=0.6))
    assert response.schema_version == "1.0"
    assert response.authority == "evidence_only"
    assert response.decision_binding is False
    assert response.items
    linked = [ref for item in response.items for ref in item.evidence["loop_trace_refs"]]
    assert any(x["run_id"] == "r1" and x["iteration_count"] == 2 for x in linked)
    assert all("action" not in item.evidence for item in response.items)
