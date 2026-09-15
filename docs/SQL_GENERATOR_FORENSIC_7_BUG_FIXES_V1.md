# ITXN Stage 4 — SQL Generator Forensic 7-Bug Hardening

Date: 2026-09-06

## Review result against v3.1

The previous v3.1 ZIP was inspected directly. Six of the seven reported stress-test bugs were present in that release. Bug #6 (list/tuple `IN (...)`) had already been fixed in v3.1 and was retained as a protected regression contract.

## Fixes

1. **Missing join for filter tables** — aggregate filters now resolve required joins from a semantic-layer `join_graph`. The generator never invents arbitrary joins.
2. **Wrong `time_of_day` semantics** — filters now use `dim_time.hour24`; ranges are morning 5–11, afternoon 12–16, evening 17–20, night 21–4.
3. **Boolean / amount / error filters** — added typed predicates for `is_approved`, `has_error`, `is_stuck`, `is_hot_card`, `min_amount`, `max_amount`, and `err_severity` / `error_severity`.
4. **Missing `terminal_risk_score`** — added to the transaction detail allow-list and resolved from `dim_terminal`.
5. **Dictionary ranges** — `hour24: {from,to}` and `date_range: {from,to}` are explicitly parsed and validated; invalid ranges fail closed.
6. **List filters** — list/tuple values remain deterministic `IN (...)` predicates with typed literal validation and SQL quote escaping.
7. **Relative-date reference** — `SQLGenerator.generate(..., reference_date=...)` and `context["reference_date"]` allow reproducible test/demo windows while preserving the original positional `context` argument.

## Verification

- Focused regression tests: **17/17 PASS**
- Full pytest: **70 passed, 3 skipped**
- Aggregate golden: **8/8 PASS**
- Detail/Top-N golden: **2/2 PASS**
- Security static audit: **PASS**
- Performance smoke: **PASS**
- Release gate: **0 code failures; 1 environment block** because DuckDB, SQLGlot, OpenAI and Docker are unavailable in the sandbox.

## Runtime certification boundary

DuckDB execution itself could not be re-run in this environment because the `duckdb` package and binary are unavailable and package installation is blocked by outbound DNS restrictions. The generated SQL contracts, regression tests, semantic-join resolution, and all available deterministic verification gates were run successfully.
