# Detail / Top-N Final Implementation Report

Date: 2026-09-07

## Result

ITXN Stage 4 now supports bounded forensic transaction queries without introducing SQL-generation heuristics or changing the agentic/SML architecture.

## Delivered

- Explicit `Intent.query_type`: `aggregate`, `detail`, `top_n_detail`, `top_n_aggregate`.
- Semantic `transaction` detail view with allow-listed fields and joins.
- Deterministic detail SQL template.
- Strict semantic order-by and limit handling.
- `TOP_N_DETAIL` invariant: no aggregate functions and no `GROUP BY`.
- Query-shape aware SQL review correction via `suggested_query_type`.
- Normal and memory-aware intent extraction updated to preserve query shape.
- Semantic-layer context supplied to intent extraction.
- Query-type persistence added to SQLite memory records with backward-compatible schema migration.
- Existing aggregate golden corpus unchanged: 8/8.
- New detail/Top-N corpus: 2/2.

## Safety

Arbitrary detail fields, arbitrary joins, arbitrary ORDER BY expressions, unbounded detail requests, and customer fields absent from the authoritative schema are rejected rather than guessed.

## Repository verification

`pytest -q`: 53 passed, 3 skipped.

## Post-freeze regression fix — list-valued entity filters

A real execution regression was identified after the Detail/Top-N extension: list-valued intent entities were serialized with `str(value)` and then quoted as a scalar equality, producing invalid semantics such as `dim_server.server_type = '['Primary', 'Backup']'`.

The deterministic filter builder now treats `list` and `tuple` entity values as collections and emits semantic `IN (...)` predicates. String members are SQL-quoted with embedded single quotes escaped; integer members remain unquoted. Scalar string behavior remains `column = 'value'`. The same implementation is used by both aggregate and detail paths. Empty collections and invalid typed members fail closed.

Regression coverage was added for aggregate string lists, detail tuple lists, numeric lists, scalar backward compatibility, and SQL quote escaping.

`compileall`: PASS.

Security static audit: PASS; 0 source-store write violations and 0 forbidden Core imports.

SML performance smoke: PASS in the available sandbox.

Release gate: 0 code failures, 1 environment block (`duckdb`, `sqlglot`, `openai` unavailable in sandbox).

## Post-freeze forensic filter hardening

Seven real-execution issues were reviewed against the v3.1 release. The review confirmed six issues were present in the release, while list/tuple `IN (...)` handling was already fixed in v3.1. The implementation was then extended to close all seven requested contracts without changing the deterministic SQL-generation boundary.

- Filter-required dimension joins are resolved only from the semantic-layer-approved join graph.
- `time_of_day` uses `dim_time.hour24`: morning 5-11, afternoon 12-16, evening 17-20, night 21-4.
- Boolean and amount entities are rendered as typed predicates; `err_severity` uses `dim_error`.
- `terminal_risk_score` is now an allow-listed transaction detail field backed by `dim_terminal.terminal_risk_score`.
- Dictionary range entities are handled explicitly for `hour24` and `date_range`; malformed ranges fail closed.
- Existing list/tuple `IN (...)` semantics remain intact.
- `SQLGenerator.generate(..., reference_date=...)` provides deterministic relative-date testing; `context["reference_date"]` is also accepted for compatibility.

Verification: **78 passed, 3 skipped**, aggregate golden **8/8**, Detail/Top-N golden **2/2**, security audit **PASS**, performance smoke **PASS**, release gate **0 failures / 1 environment block**.


## Final stress-test hardening

The next execution-stress pass identified missing weekend/holiday predicates, case-sensitive enum filters, a missing `is_hot_card` detail field, and unnecessary detail joins. These are now closed.

- `is_weekend` / `is_holiday` are typed boolean filters and trigger the approved `dim_date` join.
- Enum-like strings are normalized through semantic-layer `canonical_values`, so `completed` resolves to `Completed` and `chip` to `Chip` without wrapping indexed columns in `LOWER()`.
- `is_hot_card` is an allow-listed detail field.
- Detail joins are dependency-driven from selected semantic fields plus filter requirements instead of joining the entire view graph.

Final verification: **78 passed, 3 skipped**, aggregate golden **8/8**, Detail/Top-N golden **2/2**, security **PASS**, performance smoke **PASS**, release gate **0 code failures / 1 environment block**.
