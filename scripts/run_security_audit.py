"""Static security contract audit for release verification."""
from __future__ import annotations
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]

RULES=[
    (ROOT/'sml', r'\b(INSERT|UPDATE|DELETE)\s+INTO?\s+(memory|agent_alerts|agent_state)', 'SML writes to source databases'),
    (ROOT/'evolution', r'\b(INSERT|UPDATE|DELETE)\s+INTO?\s+(memory|agent_alerts|agent_state)', 'Evolution writes to source databases'),
]

def main():
    failures=[]
    for base, pattern, reason in RULES:
        for p in base.rglob('*.py'):
            text=p.read_text(encoding='utf-8')
            if re.search(pattern,text,re.I): failures.append((p.relative_to(ROOT),reason))
    forbidden=[]
    for p in (ROOT/'src').rglob('*.py'):
        text=p.read_text(encoding='utf-8')
        if re.search(r'\b(import|from)\s+(sml|evolution)\b', text): forbidden.append(p.relative_to(ROOT))
    print('SECURITY AUDIT')
    print('source-store write violations:', len(failures))
    print('core extension imports:', len(forbidden))
    if failures: print(*failures, sep='\n')
    if forbidden: print(*forbidden, sep='\n')
    return 1 if failures or forbidden else 0
if __name__=='__main__': raise SystemExit(main())
