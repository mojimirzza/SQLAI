# Final Build Report — ITXN Stage 4 + P0 Hardening

## Scope

This repository preserves the Stage 4 Core and adds the implemented RFC-003 Situation Memory Layer and RFC-001 Evidence → Hypothesis → Council → Governance flow without putting either learning layer on the primary user response path.

## P0 hardening completed

- Canonical API entrypoint now delegates to the enriched Stage-4 application (`src.api.main:app` → `main_enriched.app`).
- `run.py` uses the same canonical API surface.
- Primary Sidecar follow-up dispatch uses `trigger_suggest_async()` after durable query persistence.
- SML stores multiple signals per Situation with idempotent source identity.
- SML records Situation lifecycle events for auditability.
- SML populates temporal/family relationship edges.
- Pattern Family lifecycle persists CANDIDATE → SHADOW → VALIDATED → ACTIVE and guarded DEPRECATED/REVOKED transitions.
- Evidence Builder validates required fields, traceability, independent sources and confidence.
- Hypothesis generation is evidence-driven rather than a fixed three-item output.
- Council records role-specific evidence-backed arguments and counterarguments.
- Governance verifies proposal existence and prevents repeat decisions; it never auto-approves production changes.

## Verification

- `pytest -q` → **70 passed, 3 skipped**
- `python -m compileall -q .` → **PASS**
- Static check: no `sml` / `evolution` imports from `src/` / `agent/` / `sidecar/` core paths.
- Primary orchestration uses the asynchronous Sidecar suggestion helper.

## Known non-P0 deployment work

- Durable production event bus/outbox remains future hardening.
- External IdP integration remains deployment-owned.
- Full golden fixture corpus requires deployment verification.
- Production-scale load/latency testing requires the target environment and full runtime dependencies.


## Item 3 Completion
The SML → ReAct A/B evaluation harness, CLI runner, test, and release documentation were added. Full pytest passes with 37 passed / 3 skipped / 0 failed. Release gate reports 0 failures and 1 environment-blocked dependency check.


## Final Freeze v2 — Agentic Loop Integration

- Sidecar anomaly investigation now uses the bounded ReAct loop with persisted iteration state and replay support.
- SML remains deterministic and evidence-only; it is not an LLM decision-maker.
- SML exposes bounded historical context to Sidecar through a read-only, fail-safe provider.
- SML worker has bounded backoff and graceful shutdown.
- Situation records can retain trace references back to Sidecar investigation/run/iteration history.
- Main Chain remains isolated and unchanged.

## Detail / Top-N query-shape extension

- Added explicit `Intent.query_type`: `aggregate`, `detail`, `top_n_detail`, `top_n_aggregate`.
- Added semantic-layer-controlled `transaction` detail view with bounded field/join allow-list and `max_limit=100`.
- Added deterministic detail SQL template; LLM remains an intent classifier only.
- Added strict semantic order/limit validation and no-aggregation invariant for `TOP_N_DETAIL`.
- Added backward-compatible query-type persistence to SQLite memory records.
- Existing aggregate path and 8-question golden corpus remain unchanged and pass 8/8.
- New Detail/Top-N golden fixtures pass 2/2.


## Forensic SQL Generator Hardening — v3.2

- Audited the previous v3.1 release against seven DuckDB stress-test findings.
- Implemented semantic join auto-resolution for filter-required dimensions.
- Corrected time-of-day semantics to `dim_time.hour24`.
- Added boolean, amount, and error-severity filters.
- Added `terminal_risk_score` to the detail projection allow-list.
- Added dictionary range filters for `hour24` and `date_range`.
- Preserved list/tuple `IN (...)` regression fix.
- Added `reference_date` injection for deterministic relative-date tests.
- Regression suite: 18 focused tests; full suite: 78 passed, 3 skipped.


## Final Stress-Test Hardening — v3.3

- Added `is_weekend` and `is_holiday` typed boolean filters with semantic `dim_date` joins.
- Added semantic-layer canonical enum spellings for case-insensitive intent normalization while preserving index-friendly equality predicates.
- Added `is_hot_card` to the transaction detail projection allow-list.
- Optimized detail query joins to include only tables required by requested fields or filter entities.
- Preserved the deterministic SQL-generation contract; no arbitrary joins or SQL expressions are accepted.

## Final verification

- `pytest -q` → **78 passed, 3 skipped**
- Aggregate golden → **8/8**
- Detail/Top-N golden → **2/2**
- Security audit → **PASS**
- Performance smoke → **PASS**
- Release gate → **0 failures / 1 environment block**
