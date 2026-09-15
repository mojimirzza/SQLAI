"""Deterministic, bounded SML performance smoke benchmark using SQLite fixtures only."""
from __future__ import annotations
import json, sqlite3, statistics, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sml.storage import SituationStore
from sml.correlator import SituationCorrelator

RUNS = 3
SIGNALS_PER_RUN = 100

def setup(root: Path, n: int):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    mem = root/'memory.db'; alerts = root/'alerts.db'; state = root/'state.db'; sit = root/'situation.db'
    with sqlite3.connect(mem) as c:
        c.execute('CREATE TABLE query_records (id TEXT PRIMARY KEY,user_id TEXT,session_id TEXT,query_text TEXT,timestamp TEXT,intent_category TEXT,intent_entities TEXT,generated_sql TEXT,sql_metric TEXT,sql_dimensions TEXT,sql_filters TEXT,sql_joins TEXT,execution_row_count INTEGER,execution_success INTEGER,response_type TEXT,confidence REAL)')
        ts = now.isoformat()
        for i in range(n):
            c.execute('INSERT INTO query_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (f'q{i}','u','s','latency',ts,'avg_switch_latency',
                       json.dumps({'server':['SRV-A']}),'SELECT 1','avg_switch_latency',
                       '["server"]','[]','[]',1,1,'sql_only',.9))
    with sqlite3.connect(alerts) as c:
        c.execute('CREATE TABLE alert_log (alert_id TEXT PRIMARY KEY,triggered_at TEXT,metric_name TEXT,server_sk INTEGER,severity TEXT,message TEXT,decision_reasoning TEXT,action_taken TEXT,sent_successfully INTEGER,acknowledged_at TEXT,resolved_at TEXT,was_real_incident INTEGER,false_positive INTEGER)')
    with sqlite3.connect(state) as c:
        c.execute('CREATE TABLE investigations (id TEXT PRIMARY KEY,query_id TEXT,triggered_at TEXT,hypothesis TEXT,confidence TEXT,drilldown_count INTEGER,report_path TEXT,status TEXT,resolved_at TEXT)')
    return mem, alerts, state, sit

def pct(values, p):
    values = sorted(values)
    if not values: return 0.0
    idx = (len(values)-1)*p
    lo, hi = int(idx), min(int(idx)+1, len(values)-1)
    return values[lo] + (values[hi]-values[lo])*(idx-lo)

def main():
    samples = []
    for _ in range(RUNS):
        with tempfile.TemporaryDirectory() as d:
            mem, alerts, state, sit = setup(Path(d), SIGNALS_PER_RUN)
            store = SituationStore(str(sit))
            corr = SituationCorrelator(store, str(mem), str(alerts), str(state))
            t0 = time.perf_counter()
            result = corr.run_once(lookback_minutes=2)
            elapsed = time.perf_counter() - t0
            if result.get('errors') or result.get('signals_seen') != SIGNALS_PER_RUN:
                print('ERROR', result)
                return 1
            samples.append(elapsed)
    print(f'runs={RUNS} signals_per_run={SIGNALS_PER_RUN}')
    print(f'p50_s={pct(samples,.50):.4f} p95_s={pct(samples,.95):.4f} p99_s={pct(samples,.99):.4f}')
    print(f'mean_s={statistics.mean(samples):.4f}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
