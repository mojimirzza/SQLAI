from __future__ import annotations
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sml.storage import SituationStore
from sml.correlator import SituationCorrelator
from evolution.storage import EvolutionStore
from evolution.evidence_builder import EvidenceBuilder
from evolution.hypothesis import HypothesisGenerator
from evolution.council import Council
from evolution.proposals import ProposalBuilder


def _make_memory(path, when, query_id="q1"):
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE query_records (id TEXT PRIMARY KEY,user_id TEXT,session_id TEXT,query_text TEXT,timestamp TEXT,intent_category TEXT,intent_entities TEXT,generated_sql TEXT,sql_metric TEXT,sql_dimensions TEXT,sql_filters TEXT,sql_joins TEXT,execution_row_count INTEGER,execution_success INTEGER,response_type TEXT,confidence REAL)")
        c.execute("INSERT INTO query_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(query_id,"u","s","slow Tehran transactions",when.isoformat(),"avg_switch_latency",json.dumps({"server":["SRV-A"],"bank":["Mellat"]}),"SELECT 1","avg_switch_latency","[\"server\"]","[]","[]",1,1,"sql_only",.9))

def _make_alert(path, when):
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE alert_log (alert_id TEXT PRIMARY KEY,triggered_at TEXT,metric_name TEXT,server_sk INTEGER,severity TEXT,message TEXT,decision_reasoning TEXT,action_taken TEXT,sent_successfully INTEGER,acknowledged_at TEXT,resolved_at TEXT,was_real_incident INTEGER,false_positive INTEGER)")
        c.execute("INSERT INTO alert_log VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",("a1",when.isoformat(),"avg_switch_latency",1,"medium","latency spike","z","alert",1,None,None,1,0))

def _make_state(path, when):
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE investigations (id TEXT PRIMARY KEY,query_id TEXT,triggered_at TEXT,hypothesis TEXT,confidence TEXT,drilldown_count INTEGER,report_path TEXT,status TEXT,resolved_at TEXT)")
        c.execute("INSERT INTO investigations VALUES (?,?,?,?,?,?,?,?,?)",("i1","q1",when.isoformat(),"Mellat timeout","high",1,"r.md","resolved",when.isoformat()))


def test_sml_to_council_pipeline(tmp_path: Path):
    base = datetime.now(timezone.utc).replace(microsecond=0)
    mem=tmp_path/"memory.db"; alerts=tmp_path/"agent_alerts.db"; state=tmp_path/"agent_state.db"; sit=tmp_path/"situation_memory.db"; evo=tmp_path/"knowledge_evolution.db"
    _make_memory(mem,base); _make_alert(alerts,base+timedelta(minutes=1)); _make_state(state,base+timedelta(minutes=2))
    ss=SituationStore(str(sit)); result=SituationCorrelator(ss,str(mem),str(alerts),str(state)).run_once(lookback_minutes=10)
    assert result["errors"] == 0
    situations=ss.recent_situations(10)
    assert len(situations) >= 1
    # At least one situation should contain signals from multiple systems.
    multi=[x for x in situations if x["signal_count"] >= 2]
    assert multi
    ev=EvolutionStore(str(evo)); evidence=EvidenceBuilder(ss,ev).build_for_situation(multi[0]["situation_id"])
    assert evidence["status"] == "accepted"
    hyps=HypothesisGenerator(ev).generate(evidence)
    council=Council(ev).deliberate(evidence,hyps)
    winner=next(h for h in hyps if h["hypothesis_id"]==council["winning_hypothesis_id"])
    proposal=ProposalBuilder(ev).build(council,winner,evidence)
    assert proposal["status"] == "pending"


def test_three_signal_convergence_to_one_situation(tmp_path):
    """P0.3 — Query + Alert + Investigation must converge to exactly ONE Situation."""
    from datetime import datetime, timezone
    import sqlite3
    import json

    now = datetime.now(timezone.utc)
    memory_db = str(tmp_path / "memory.db")
    alert_db = str(tmp_path / "agent_alerts.db")
    state_db = str(tmp_path / "agent_state.db")
    sml_db = str(tmp_path / "sml.db")

    # 1 query record with server in intent_entities
    with sqlite3.connect(memory_db) as c:
        c.execute("CREATE TABLE query_records (id TEXT PRIMARY KEY,user_id TEXT,session_id TEXT,query_text TEXT,timestamp TEXT,intent_category TEXT,intent_entities TEXT,generated_sql TEXT,sql_metric TEXT,sql_dimensions TEXT,sql_filters TEXT,sql_joins TEXT,execution_row_count INTEGER,execution_success INTEGER,response_type TEXT,confidence REAL)")
        c.execute("INSERT INTO query_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("q1","u","s","slow Tehran transactions",now.isoformat(),"avg_switch_latency",
             json.dumps({"server":["SRV-A"],"bank":["Mellat"]}),"SELECT 1",
             "avg_switch_latency",'[\"server\"]','[]','[]',1,1,"sql_only",.9))

    # 1 alert on same metric
    with sqlite3.connect(alert_db) as c:
        c.execute("CREATE TABLE alert_log (alert_id TEXT PRIMARY KEY,triggered_at TEXT,metric_name TEXT,server_sk INTEGER,severity TEXT,message TEXT,decision_reasoning TEXT,action_taken TEXT,sent_successfully INTEGER,acknowledged_at TEXT,resolved_at TEXT,was_real_incident INTEGER,false_positive INTEGER)")
        c.execute("INSERT INTO alert_log VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("a1",now.isoformat(),"avg_switch_latency",1,"medium","latency spike","z","alert",1,None,None,1,0))

    # 1 investigation pointing back to query
    with sqlite3.connect(state_db) as c:
        c.execute("CREATE TABLE investigations (id TEXT PRIMARY KEY,query_id TEXT,triggered_at TEXT,hypothesis TEXT,confidence TEXT,drilldown_count INTEGER,report_path TEXT,status TEXT,resolved_at TEXT)")
        c.execute("INSERT INTO investigations VALUES (?,?,?,?,?,?,?,?,?)",
            ("i1","q1",now.isoformat(),"Mellat timeout","high",1,"r.md","resolved",now.isoformat()))

    from sml.storage import SituationStore
    from sml.correlator import SituationCorrelator

    store = SituationStore(sml_db)
    store.init_schema()
    corr = SituationCorrelator(store, memory_db, alert_db, state_db, window_seconds=900, threshold=0.60)
    result = corr.run_once(lookback_minutes=30)

    # Assertions
    assert result["signals_seen"] == 3, f"Expected 3 signals, got {result['signals_seen']}"
    assert result["errors"] == 0

    situations = store.list_situations()
    assert len(situations) == 1, f"Expected exactly 1 Situation, got {len(situations)}: {situations}"

    sigs = store.signals_for_situation(situations[0][0])
    source_systems = {s[3] for s in sigs}
    assert source_systems == {"src", "agents", "sidecar"}, f"Missing sources: {source_systems}"
    assert len(sigs) >= 3, f"Expected >=3 signals in Situation, got {len(sigs)}"
