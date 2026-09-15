#!/usr/bin/env python3
"""One-shot Codespaces initialization for the complete ITXN lab."""
from __future__ import annotations
import os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
os.chdir(ROOT)
Path('data').mkdir(exist_ok=True)

def run(args:list[str]) -> None:
    print('$', ' '.join(args), flush=True)
    subprocess.run(args, check=True)

run([sys.executable, 'scripts/init_db.py'])
run([sys.executable, 'scripts/unified_setup.py'])
run([sys.executable, 'scripts/seed_mobile_lab.py'])
print('CODESPACE_SETUP_OK')
