#!/usr/bin/env python3
"""Replay a persisted Sidecar investigation trace without tools or LLM calls."""
from __future__ import annotations
import argparse, json, sqlite3
from pathlib import Path
from sidecar.core.loop_engineering import LoopReplay, LoopVerifier

def main() -> int:
    p=argparse.ArgumentParser(description='Replay a Sidecar ReAct investigation trace')
    p.add_argument('--state-db', default='data/agent_state.db')
    p.add_argument('--run-id', required=True)
    args=p.parse_args()
    db=Path(args.state_db)
    if not db.is_file():
        p.error(f'state DB not found: {db}')
    with sqlite3.connect(f'file:{db.resolve()}?mode=ro', uri=True) as conn:
        conn.row_factory=sqlite3.Row
        rows=[dict(r) for r in conn.execute('SELECT * FROM agent_iterations WHERE run_id=? ORDER BY iteration_no',(args.run_id,)).fetchall()]
    verification=LoopVerifier().verify_trace(rows)
    replay=LoopReplay().replay(rows)
    print(json.dumps({'status':verification.status,'reason':verification.reason,'run_id':args.run_id,'iterations':replay},ensure_ascii=False,indent=2,sort_keys=True))
    return 0 if verification.status == 'passed' else 1
if __name__=='__main__': raise SystemExit(main())
