# ITXN Stage 4 — List-Valued Entity Filter Regression Fix

**Date:** 2026-09-06

## Incident

After the Detail/Top-N refactor, real execution testing exposed a semantic regression in `src/core/sql_generator.py`: a list-valued intent entity was converted with `str(value)` and quoted as one scalar.

Example bad output:

```sql
WHERE dim_server.server_type = '[''Primary', ''Backup'\]'
```

Expected:

```sql
WHERE dim_server.server_type IN ('Primary', 'Backup')
```

## Fix

`_build_filters()` and `_build_filters_for_detail()` now share a deterministic typed entity-filter implementation:

- `list` / `tuple` → `IN (...)`
- string members → quoted and SQL-escaped
- integer members → unquoted
- scalar strings → existing `=` behavior
- empty collections → rejected
- invalid typed values → rejected

No SQL generation authority was added to the LLM. The semantic/deterministic generation contract is unchanged.

## Verification

- `pytest -q`: **53 passed, 3 skipped**
- aggregate golden: **8/8 passed**
- Detail/Top-N golden: **2/2 passed**
- compileall: **PASS**
- security audit: **PASS**
- release gate: **0 code failures; 1 environment block** (`duckdb`, `sqlglot`, `openai` unavailable in sandbox)
