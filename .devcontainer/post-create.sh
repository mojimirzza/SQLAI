#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/codespace_setup.py
printf '\nITXN Codespace ready.\nRun: bash scripts/codespace_up.sh\nOr verify: python scripts/full_system_verdict.py\n'
