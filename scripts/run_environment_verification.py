"""Environment-complete verification. Uses declared dependencies when available."""
from __future__ import annotations
import importlib.util, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(cmd):
    return subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)

def main():
    required=['duckdb','sqlglot','openai']
    missing=[x for x in required if importlib.util.find_spec(x) is None]
    print('MISSING=' + ','.join(missing) if missing else 'DEPENDENCIES=OK')
    if missing:
        print('BLOCKED: install declared runtime dependencies and rerun')
        return 2
    init=run([sys.executable,'scripts/init_db.py'])
    print('INIT_DB_RC=',init.returncode); print((init.stdout+init.stderr)[-4000:])
    if init.returncode: return 1
    gold=run([sys.executable,'scripts/run_golden_tests.py'])
    print((gold.stdout+gold.stderr)[-4000:])
    if gold.returncode: return 1
    return 0
if __name__=='__main__': raise SystemExit(main())
