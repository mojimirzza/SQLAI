from __future__ import annotations
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

from sml.storage import SituationStore
from sml.correlator import SituationCorrelator


def _setup_fixture(tmp_path: Path):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    mem = tmp_path / 'memory.db'; alerts = tmp_path / 'agent_alerts.db'; state = tmp_path / 'agent_state.db'
    with sqlite3.connect(mem) as c:
        c.execute('CREATE TABLE query_records (id TEXT PRIMARY KEY,user_id TEXT,session_id TEXT,query_text TEXT,timestamp TEXT,intent_category TEXT,intent_entities TEXT,generated_sql TEXT,sql_metric TEXT,sql_dimensions TEXT,sql_filters TEXT,sql_joins TEXT,execution_row_count INTEGER,execution_success INTEGER,response_type TEXT,confidence REAL)')
        c.execute('INSERT INTO query_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', ('q1','u','s','slow Tehran',now.isoformat(),'avg_switch_latency',json.dumps({'server':['SRV-A'],'bank':['Mellat']}),'SELECT 1','avg_switch_latency','["server"]','[]','[]',1,1,'sql_only',.9))
    with sqlite3.connect(alerts) as c:
        c.execute('CREATE TABLE alert_log (alert_id TEXT PRIMARY KEY,triggered_at TEXT,metric_name TEXT,server_sk INTEGER,severity TEXT,message TEXT,decision_reasoning TEXT,action_taken TEXT,sent_successfully INTEGER,acknowledged_at TEXT,resolved_at TEXT,was_real_incident INTEGER,false_positive INTEGER)')
        c.execute('INSERT INTO alert_log VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', ('a1',now.isoformat(),'avg_switch_latency',1,'medium','latency spike','z','alert',1,None,now.isoformat(),1,0))
    with sqlite3.connect(state) as c:
        c.execute('CREATE TABLE investigations (id TEXT PRIMARY KEY,query_id TEXT,triggered_at TEXT,hypothesis TEXT,confidence TEXT,drilldown_count INTEGER,report_path TEXT,status TEXT,resolved_at TEXT)')
        c.execute('INSERT INTO investigations VALUES (?,?,?,?,?,?,?,?,?)', ('i1','q1',now.isoformat(),'Mellat timeout','high',1,'r.md','resolved',now.isoformat()))
    return now, mem, alerts, state


def test_three_source_systems_converge_to_one_situation(tmp_path: Path):
    _, mem, alerts, state = _setup_fixture(tmp_path)
    store = SituationStore(str(tmp_path / 'situation.db'))
    result = SituationCorrelator(store, str(mem), str(alerts), str(state)).run_once(lookback_minutes=10)
    assert result['signals_seen'] == 3
    assert result['errors'] == 0
    situations = store.recent_situations()
    assert len(situations) == 1
    signals = store.signals_for_situation(situations[0]['situation_id'])
    assert {row[3] for row in signals} == {'src', 'agents', 'sidecar'}
    assert len(signals) == 3


def test_correlation_is_idempotent(tmp_path: Path):
    _, mem, alerts, state = _setup_fixture(tmp_path)
    store = SituationStore(str(tmp_path / 'situation.db'))
    c = SituationCorrelator(store, str(mem), str(alerts), str(state))
    first = c.run_once(lookback_minutes=10)
    second = c.run_once(lookback_minutes=10)
    assert first['errors'] == second['errors'] == 0
    assert len(store.recent_situations()) == 1
    assert len(store.signals_for_situation(store.recent_situations()[0]['situation_id'])) == 3


def test_sml_sources_are_write_protected_by_code_contract():
    source = ''.join(p.read_text(encoding='utf-8') for p in Path('sml').rglob('*.py'))
    assert 'INSERT INTO memory.' not in source
    assert 'INSERT INTO agent_alerts' not in source
    assert 'UPDATE memory.' not in source
    assert 'DELETE FROM memory.' not in source
