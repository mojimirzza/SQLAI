# Mobile Lab — Verification Status

Generated from the supplied Stage-4 ZIP.

## Verified inside the sandbox

- 70 project tests passed after the mobile/agent hardening patch.
- 4 additional Sidecar Stage-4 tests passed.
- Python compilation passed for the patched Agent/mobile-lab files.

The verified deterministic path covers:

`SML correlation/storage → Evidence Package → Hypothesis Generator → Council → Proposal → Situation Memory contract → Loop verifier/evaluator/replay → ReAct contract`

## Important corrections found in the supplied build

1. `agent/tools/query_baseline.py` opened `data/bank.duckdb` through SQLite. The mobile-lab patch switches this warehouse read to DuckDB read-only mode.
2. `agent/agent_loop.py` also opened the DuckDB warehouse through SQLite for anomaly updates. The patch switches this connection to DuckDB.
3. The supplied `scripts/init_db.py` did not create the `metric_daily_baseline` table even though the Agent depends on it. The new `scripts/seed_mobile_lab.py` creates and seeds this table.
4. The supplied demo calendar was frozen around 2026-08-12. The mobile lab adds current dates and current-date sample transactions so relative-date prompts can be demonstrated.
5. The following components are deterministic in the supplied implementation and do not require an LLM: Pattern Analyzer, Evidence Builder, Hypothesis Generator, and Council.

## Not claimed as verified here

A live OpenAI call and real DuckDB execution could not be performed in this sandbox because the environment has no package-install/network access for the missing `openai`, `duckdb`, and `sqlglot` packages. The API key pasted into chat was intentionally not used.

The real-cloud validation step is therefore explicitly:

`Browser → FastAPI mobile UI → OpenAI → deterministic SQL → SQLGlot → DuckDB → baseline → BA/CEO → async Sidecar`.

The intended environment for this is a browser-based cloud runtime such as GitHub Codespaces or Replit.
