#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p data/logs

if [ -z "${OPENROUTER_API_KEY:-}" ] && [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "ERROR: set OPENROUTER_API_KEY (recommended) or OPENAI_API_KEY in Codespaces Secrets."
  exit 2
fi

export OPENROUTER_BASE_URL="${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}"
export OPENROUTER_MODEL="${OPENROUTER_MODEL:-openai/gpt-4o-mini}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-$OPENROUTER_BASE_URL}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-${OPENROUTER_API_KEY:-}}"
export OPENAI_MODEL="${OPENAI_MODEL:-$OPENROUTER_MODEL}"
export SIDECAR_MODEL="${SIDECAR_MODEL:-$OPENROUTER_MODEL}"

pkill -f 'uvicorn.*mobile_app:app' 2>/dev/null || true
nohup python -m uvicorn mobile_app:app --host 0.0.0.0 --port 8000 > data/logs/api.log 2>&1 &
echo $! > data/logs/api.pid
sleep 2

echo "ITXN API running on port 8000"
echo "Use the Codespaces forwarded URL from the Ports panel."
echo "Run the complete verdict with: python scripts/full_system_verdict.py --live"
