# ITXN Stage 4 — Final Release Freeze

Date: 2026-09-07

## Freeze decision

**FUNCTIONAL / ARCHITECTURAL RELEASE: FROZEN — GREEN**

**PRODUCTION RUNTIME CERTIFICATION: BLOCKED BY ENVIRONMENT**

No code-level failures remain in the available verification environment. The release candidate is frozen at this revision; the accepted agentic-loop branch and bounded Detail/Top-N + forensic filter hardening are merged without changing the Core architectural boundary or adding an LLM SQL author.

## Verification executed

- Python compileall: PASS
- Full pytest: PASS — 78 passed, 3 skipped, 0 failed
- Deterministic aggregate golden suite: PASS — 8/8
- Deterministic Detail/Top-N golden suite: PASS — 2/2
- Security static audit: PASS — 0 source-store write violations; 0 core-extension imports
- SML performance smoke: PASS — p95 below 0.17s for 3x100-signal runs
- Release-candidate gate: 0 failures, 1 blocked
- Canonical API entrypoint: PASS
- `src/` isolation: PASS
- Source-tree cleanliness: PASS
- `src/**/*.py` before/after hash comparison: IDENTICAL

## Forensic filter hardening included in this freeze

- Semantic filter auto-joins
- Dimension-backed `time_of_day` filters
- Boolean/amount/error filters
- Detail `terminal_risk_score` allow-list
- Dictionary range filters
- List/tuple `IN (...)` filters
- Reproducible `reference_date` for relative time ranges

## Explicit skips / blocked checks

The three skipped tests require `openai` and/or `duckdb`.
The environment-complete gate is blocked because `duckdb`, `sqlglot`, `openai`, and Docker are not available in the current sandbox. Package installation was attempted but outbound DNS/package access is unavailable.

These conditions are **not reclassified as PASS** and are not code failures.

## Freeze rules

- `src/` remains unchanged.
- Sidecar ReAct is the bounded investigation decision loop.
- SML is deterministic/resilient/evidence-only; it is not an LLM decision loop.
- SML remains asynchronous, read-only against source stores, and evidence-only.
- ReAct remains the decision-maker for investigation behavior.
- Governance remains the authority for operational/knowledge changes.
- No production playbook mutation is introduced by SML.
- Future production deployment must run the environment-complete verification runbook before being labeled production-certified.
