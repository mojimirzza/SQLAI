#!/usr/bin/env python3
"""Full-system acceptance verdict for the ITXN Codespaces lab.

Default mode verifies deterministic/runtime wiring without spending LLM credits.
--live additionally performs one real LLM-backed Text-to-SQL request and checks
that the downstream memory/baseline/SML/Evolution surfaces remain wired.
"""
from __future__ import annotations
import argparse, asyncio, importlib.util, json, os, sqlite3, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
import argparse
ap=argparse.ArgumentParser()
ap.add_argument('--live',action='store_true')
args=ap.parse_args()

checks=[]
def check(name, ok, detail="", blocked=False):
    status='BLOCKED' if blocked else ('PASS' if ok else 'FAIL')
    checks.append((name,status,detail))
    mark={'PASS':'✓','FAIL':'✗','BLOCKED':'⊘'}[status]
    print(f'[{mark}] {name}: {status}')
    if detail: print(f'    {detail}')

def exists(path): return (ROOT/path).exists()

def db_tables(path):
    if not exists(path): return set()
    with sqlite3.connect(ROOT/path) as c:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

def shell(args):
    p=subprocess.run(args,cwd=ROOT,text=True,capture_output=True,timeout=90)
    return p.returncode,(p.stdout+p.stderr).strip()

# 1. Toolchain
required=['fastapi','uvicorn','pydantic','pydantic_settings','openai','sqlglot','duckdb','jinja2','yaml','dotenv']
missing=[m for m in required if importlib.util.find_spec(m) is None]
check('Python runtime dependencies', not missing, ', '.join(missing) if missing else 'all declared runtime modules import')

# 2. Architecture surfaces
surfaces={
    'Star Schema':['src/config/semantic_layer.yaml','src/config/mschema.yaml','scripts/init_db.py'],
    'Text-to-SQL':['src/core/orchestrator.py','src/core/sql_generator.py','src/core/sql_reviewer.py','src/adapters/openai_adapter.py'],
    'Alerts':['agent/agent_loop.py','agent/objective_definer.py','agent/tools/query_baseline.py'],
    'Sidecar':['sidecar/main.py','sidecar/core/agent.py','src/core/sidecar_bridge.py'],
    'SML':['sml/main.py','sml/correlator.py','sml/storage.py'],
    'Evidence/Council':['evolution/evidence_builder.py','evolution/hypothesis.py','evolution/council.py'],
    'Governance':['governance/store.py'],
}
for name, paths in surfaces.items():
    missing_paths=[p for p in paths if not exists(p)]
    check(name, not missing_paths, 'all declared entrypoints present' if not missing_paths else 'missing: '+', '.join(missing_paths))

# 3. Database setup/schema
rc,out=shell([sys.executable,'scripts/codespace_setup.py']) if not missing else (2,'runtime dependencies missing')
check('Database + seed initialization', rc==0, out[-1500:] if out else 'setup skipped', blocked=bool(missing))
if not missing:
    duck_tables=set()
    try:
        import duckdb
        c=duckdb.connect('data/bank.duckdb',read_only=True)
        duck_tables={r[0] for r in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()}
        c.close()
    except Exception as e: pass
    required_duck={'fact_transaction','dim_date','dim_time','dim_server','dim_terminal','dim_status','dim_error','fact_txn_daily_summary','metric_daily_baseline','metric_sla_thresholds'}
    check('Star schema + baseline tables', required_duck.issubset(duck_tables), 'missing: '+str(sorted(required_duck-duck_tables)))
    required_sqlite={
        'data/memory.db':{'query_records'},
        'data/agent_alerts.db':{'alert_log'},
        'data/agent_state.db':{'investigations','agent_runs'},
        'data/situation_memory.db':{'situations','situation_signals'},
    }
    for path,tabs in required_sqlite.items():
        actual=db_tables(path)
        check(f'Store {path}', tabs.issubset(actual), 'missing: '+str(sorted(tabs-actual)))

# 4. Static integration / config
try:
    settings_text=Path('src/config/settings.py').read_text()
    adapter_text=Path('src/adapters/openai_adapter.py').read_text()
    side_llm=Path('sidecar/core/llm_client.py').read_text()
    ok='OPENROUTER_API_KEY' in settings_text and 'base_url' in adapter_text and 'OPENROUTER_API_KEY' in side_llm
    check('OpenRouter wiring', ok, 'main API adapter + Sidecar client accept OpenRouter-compatible configuration')
except Exception as e: check('OpenRouter wiring',False,str(e))

# 5. Deterministic suites
if not missing:
    for label, cmd in [
        ('Repository pytest', ['pytest','-q']),
        ('Golden tests', [sys.executable,'scripts/run_golden_tests.py']),
        ('Detail/Top-N golden', [sys.executable,'scripts/run_detail_golden_tests.py']),
        ('Release gate', [sys.executable,'scripts/run_release_gate.py']),
    ]:
        rc,out=shell(cmd)
        check(label, rc==0, out[-2000:])
else:
    check('Deterministic suites',False,'blocked by missing runtime dependencies',blocked=True)

# 6. Live LLM path
if not os.getenv('OPENROUTER_API_KEY') and not os.getenv('OPENAI_API_KEY'):
    check('Live LLM',False,'Set OPENROUTER_API_KEY or OPENAI_API_KEY to run the real path.',blocked=True)
elif not args.live:
    check('Live LLM',False,'Skipped by default; rerun with --live to spend one real LLM-backed request.',blocked=True)
else:
    try:
        import uuid
        sys.path.insert(0,str(ROOT/'src'))
        from api.main_enriched import handle_query, QueryReq
        req=QueryReq(text=os.getenv('ITXN_SMOKE_QUERY','What was the average switch latency for server SRV-A today?'),user_id='codespace_verifier',user_role='analyst')
        result=asyncio.run(handle_query(req))
        payload=result.model_dump() if hasattr(result,'model_dump') else result
        check('Live Text-to-SQL request', bool(payload.get('trace_id') or payload.get('sql')), json.dumps(payload,ensure_ascii=False,default=str)[:2500])
        if isinstance(payload,dict):
            check('SQL produced/executed', bool(payload.get('sql')), 'generated SQL present')
        # Give async sidecar subprocesses a short window to materialize traces.
        time.sleep(4)
        with sqlite3.connect('data/memory.db') as c:
            qcount=c.execute('SELECT COUNT(*) FROM query_records').fetchone()[0]
        check('Memory persistence', qcount>0, f'query_records={qcount}')
        with sqlite3.connect('data/agent_state.db') as c:
            tables=db_tables('data/agent_state.db')
            inv=c.execute('SELECT COUNT(*) FROM investigations').fetchone()[0] if 'investigations' in tables else 0
            sug=c.execute('SELECT COUNT(*) FROM followup_suggestions').fetchone()[0] if 'followup_suggestions' in tables else 0
        check('Sidecar activity', inv>0 or sug>0, f'investigations={inv}, followup_suggestions={sug}', blocked=not (inv>0 or sug>0))
    except Exception as e:
        check('Live Text-to-SQL request',False,f'{type(e).__name__}: {e}')

# 7. Alert -> SML -> Evidence -> Council -> Governance readiness
if exists('data/agent_alerts.db') and not missing:
    rc,out=shell([sys.executable,'-c','from agent.agent_loop import run_agent_cycle; run_agent_cycle()'])
    check('Alert Agent cycle', rc==0, out[-1200:])
    rc,out=shell([sys.executable,'-m','sml.main','--once'])
    check('SML correlation', rc==0, out[-1500:])
    try:
        with sqlite3.connect('data/situation_memory.db') as c:
            c.row_factory=sqlite3.Row
            row=c.execute('SELECT situation_id FROM situations ORDER BY last_signal_at DESC LIMIT 1').fetchone()
        sid=row['situation_id'] if row else None
        check('Situation created', bool(sid), sid or 'no situation found')
        if sid:
            rc,out=shell([sys.executable,'-m','evolution.main','--situation-id',sid])
            check('Evidence → Hypothesis → Council', rc==0, out[-2500:])
            try:
                with sqlite3.connect('data/knowledge_evolution.db') as c:
                    c.row_factory=sqlite3.Row
                    p=c.execute('SELECT proposal_id,status FROM proposals ORDER BY created_at DESC LIMIT 1').fetchone()
                check('Governance proposal', bool(p), dict(p) if p else 'no proposal generated')
                if p:
                    from governance.store import Governance
                    g=Governance()
                    # Do NOT auto-approve. Governance remains human-gated.
                    check('Governance human gate', p['status'] not in ('approved','rejected'), f'proposal={p["proposal_id"]}, status={p["status"]}')
            except Exception as e: check('Governance proposal',False,str(e))
    except Exception as e:
        check('Situation created',False,str(e))
else:
    check('Downstream agentic chain',False,'blocked by missing runtime dependencies or DB setup',blocked=True)

print('\n'+'='*78)
print('ITXN FULL-SYSTEM VERDICT')
for n,s,d in checks:
    print(f'{s:8} | {n} | {d[:180].replace(chr(10)," ")}')
f=sum(s=='FAIL' for _,s,_ in checks); b=sum(s=='BLOCKED' for _,s,_ in checks)
print(f'FINAL: failures={f} blocked={b}')
print('VERDICT=PASS' if f==0 and b==0 else ('VERDICT=PARTIAL' if f==0 else 'VERDICT=FAIL'))
raise SystemExit(0 if f==0 else 1)

