# ITXN Detail / Top-N Extension v1

## Plan-first design decision

The existing aggregate contract remains unchanged. The new capability is a query-shape extension, not a new metric category. A business metric answers **what is measured**; `query_type` answers **what shape of result is requested**.

Supported query shapes:

- `aggregate` — existing metric-driven `SUM`/`COUNT`/`AVG` path.
- `detail` — individual fact rows with bounded `LIMIT`.
- `top_n_detail` — individual fact rows ordered by a semantic-layer-approved field with bounded `LIMIT`.
- `top_n_aggregate` — existing aggregation path plus semantic ordering and bounded `LIMIT`.

The LLM/intent layer classifies query shape and fields but never writes SQL. SQLGenerator consumes the validated intent and resolves every field/order expression from the semantic layer. No heuristic SQL-generator fallback is used.

## Refactoring boundary

1. Extend `Intent` with `query_type` while preserving the existing constructor contract and aggregate categories.
2. Extend `semantic_layer.yaml` with an allow-listed `transaction` detail view containing fields, approved joins, defaults, and `max_limit`.
3. Extend `YAMLSemanticAdapter` with `DetailViewDefinition`.
4. Add a dedicated deterministic detail template in `SQLGenerator`.
5. Keep aggregate generation unchanged except for explicit `top_n_aggregate` validation.
6. Propagate `query_type` through normal and memory-aware intent extraction, logs, and query persistence.
7. Extend semantic review language for detail/Top-N correctness.

## Safety contract

- Detail fields must exist in the configured detail view.
- Ordering must reference a configured detail field; arbitrary SQL expressions are rejected.
- Detail and Top-N require an explicit positive limit.
- The detail view has a hard maximum (`100` in the release configuration).
- Approved joins come only from the detail view.
- `TOP_N_DETAIL` must not emit aggregation functions or `GROUP BY`.
- `TOP_N_AGGREGATE` continues to use metrics and grouping.
- The current schema contains no customer dimension/key suitable for a customer-level projection; requests requiring a customer field must therefore be clarified/rejected rather than inventing one.

## Example

Intent:

```yaml
category: transaction_detail
query_type: top_n_detail
entities:
  detail_view: transaction
  detail_fields: [transaction_id, transaction_amount, server_name, terminal_sk, hour24, full_date]
  time_range: last_3_days
  order_by:
    field: transaction_amount
    direction: DESC
  limit: 15
```

Expected SQL shape:

```sql
SELECT ...
FROM fact_transaction
INNER JOIN dim_date ...
INNER JOIN dim_time ...
INNER JOIN dim_server ...
LEFT JOIN dim_terminal ...
WHERE fact_transaction.date_in_sk >= ...
  AND fact_transaction.date_in_sk < ...
ORDER BY fact_transaction.txnamt DESC
LIMIT 15
```

## Verification

- Existing aggregate golden corpus remains untouched and must continue to pass 8/8.
- New deterministic detail/Top-N golden fixtures cover positive generation and safety/semantic rejection.
- Full pytest/compile/security/performance/release-gate checks remain mandatory.
