## v1.3.3 - Final SQL Generator Stress-Test Hardening

- Added `is_weekend` and `is_holiday` boolean filters backed by `dim_date`.
- Added semantic canonical-value normalization for enum-like string filters such as `lifecycle_stage` and `entry_mode_desc`, preserving index-friendly equality SQL.
- Added `is_hot_card` to the transaction detail projection allow-list.
- Optimized detail joins to include only tables required by requested fields or filters.
- Added regression coverage for all changes while preserving aggregate golden compatibility.

## v1.3.2 - SQL Generator Forensic Filter Hardening

- Fixed semantic auto-join resolution for filter-referenced dimensions that are not emitted by a metric's normal dimension path.
- Fixed `time_of_day` to use `dim_time.hour24` rather than interpreting the `time_in_sk` surrogate key as seconds-of-day.
- Added deterministic boolean filters for `is_approved`, `has_error`, `is_stuck`, and `is_hot_card`.
- Added deterministic amount bounds for `min_amount` / `max_amount`.
- Added `err_severity` alias support with semantic `dim_error` auto-join.
- Added `terminal_risk_score` to the transaction detail allow-list.
- Added structured range handling for `hour24` and `date_range` dictionary entities.
- Added optional `reference_date` to `SQLGenerator.generate()` for reproducible relative-date testing, while preserving the existing call signature.
- Preserved existing list/tuple `IN (...)` behavior from v1.3.1.
- Added regression coverage for all seven reported stress-test bugs.

## v1.3.1 - Entity list-filter regression fix

- Fixed deterministic SQL filter generation for list/tuple-valued intent entities.
- String collections now generate `IN ('...', '...')` with SQL single-quote escaping.
- Integer collections now generate unquoted numeric `IN (...)` predicates.
- Preserved scalar equality behavior for backward compatibility.
- Applied the same contract to aggregate and Detail/Top-N filter paths.
- Added regression tests for string lists, tuple inputs, numeric lists, scalar compatibility, and quote escaping.
- Invalid or empty collections fail closed instead of producing malformed SQL.

# Changelog

## v1.1.0 - SQL Reviewer integration

- Added a lightweight SQL Reviewer semantic gate after deterministic SQL generation.
- Kept the existing OpenAI model and all existing libraries; no new runtime dependency was added.
- Reviewer never writes SQL. It returns structured semantic feedback and optional intent/entity corrections.
- Added Pydantic `SQLReviewResult` for a stable reviewer contract.
- Added `SQLReviewerPort` so the reviewer can be replaced or mocked without touching orchestration.
- Added one controlled regeneration path: review -> revise intent -> deterministic Jinja2 SQL generation -> review again.
- Added reviewer trace events: review decision, intent revision, regeneration, and second review.
- Simple low-risk queries can skip review to avoid unnecessary latency/cost.
- Added unit tests covering approval, correction feedback, skip logic, and orchestrator wiring.
- Preserved the existing architecture, FastAPI API, RAG/vector adapter, semantic layer, SQLGlot validation, DuckDB execution, BA/CEO synthesis, logging, policies, Docker, and golden tests.

## v1.2.0 - Stage 4 Production Readiness

### Deterministic policy enforcement
- Added `PolicyGate` for query-role authorization, memory access control, and protected-table checks.
- Enriched API now defaults to `analyst` rather than `admin` and accepts trusted `X-User-Id` / `X-User-Role` gateway headers.
- Memory inspection is restricted to self-access or configured memory-admin roles.

### Execution and Sidecar hardening
- Fixed the Enriched Orchestrator's undefined `event_publisher` path.
- Fixed query-record lifecycle: a stable `QueryRecord` is persisted before optional Sidecar hooks, and the same record id is used for suggestions/investigation.
- Added a reusable Sidecar SQL guard using the canonical SQLGlot validator.
- Sidecar drill-downs are SELECT-only through the existing validator, allow-listed to warehouse tables, length-limited, and blocked queries are recorded instead of executed.
- Fixed missing `os` and `json` imports in Sidecar runtime paths.

### SQL contract hardening
- Unsupported dimensions now fail explicitly instead of being silently dropped.
- Explicit end dates are inclusive and normalized to an exclusive next-day boundary.
- Added deterministic support for `this_week`, `last_week`, and `last_3_months`.

### Observability
- Added a small structured observability helper for trace-scoped lifecycle events and operation timing.

### Verification
- Added Stage 4 regression tests for policy enforcement, SQL contract/date semantics, Sidecar SQL guarding, and Enriched Orchestrator record lifecycle.

## M-Schema enrichment

- Added build-time `scripts/mschema_compiler.py` for DuckDB/SQLite metadata compilation.
- Added optional `mschema.yaml` context to ContextBuilder and IntentExtractor without breaking existing constructor calls.
- Added privacy-safe sample-value allow-listing and semantic-layer-derived logical relationships.
- Added regression tests covering compilation, prompt context, and fallback-compatible integration.

## Loop Engineering Workshop — Sidecar v1

- Added auditable per-iteration state to `agent_state.db`.
- Added loop event audit trail, structural verification, evaluation, and replay utilities.
- Switched `AnomalyInvestigator` from batch drill-down execution to the shared ReAct loop.
- Added bounded drill-down budget and configurable loop max steps.
- Added acceptance tests proving action selection can adapt after observation.

## Item 3 — SML → ReAct A/B Evaluation
- Added deterministic CI-safe A/B harness comparing ReAct with and without Situation Memory.
- Added five banking-monitoring scenarios and outcome metrics.
- Added CLI runner: `python scripts/run_sml_ab_evaluation.py`.
- Added final evaluation report and regression test.
