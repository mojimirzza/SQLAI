# Architecture

```text
User
  |
  v
Intent / Planning (OpenAI)
  |
  v
Context Builder + optional RAG
  |
  v
Semantic Layer
  |
  v
Deterministic SQL Generator (Jinja2)
  |
  v
SQL Reviewer (OpenAI, structured output)
  |                 \
  | approved         \ rejected with structured corrections
  v                   v
SQLGlot Validation   Revised Intent -> SQL Generator (max one regeneration)
  |                         |
  +-----------<-------------+
  |
  v
Read-only DuckDB execution
  |
  v
BA + CEO synthesis
  |
  v
Trace / JSON logging
```

## Reviewer contract

The reviewer is a semantic gate, not a second SQL generator. It checks:
- semantic alignment with the user question;
- correct metric/category;
- dimensions and grouping;
- filters and dates;
- aggregation semantics;
- unsupported concepts.

The reviewer returns `SQLReviewResult` and can suggest a category/entity correction. The SQL generator remains deterministic and is the only component that renders executable SQL.

## Why only one regeneration?

Unbounded reflection loops increase latency, cost, and failure modes. This version allows one controlled regeneration. If the second review still rejects the query, execution stops safely.
