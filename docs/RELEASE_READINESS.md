# ITXN Stage 4 — Release Readiness Plan

## Gate sequence

1. Repository gate: compile, tests, golden, source isolation.
2. Runtime gate: declared dependencies, DB initialization, API health, real SQL execution.
3. SML/Evolution gate: three-source Situation, idempotency, Evidence→Council→Governance.
4. Security gate: read-only boundaries, policy bypass, SQL safety, sensitive-data handling.
5. Performance gate: Core p50/p95/p99, timeout enforcement, concurrency; SML throughput/backlog.
6. Deployment gate: Docker build/start, worker execution, configuration validation.
7. Go/No-Go: one signed report with PASS/FAIL/BLOCKED for every requirement.

## Required evidence

A check is PASS only when it executes successfully in the target environment. A missing dependency or unavailable external service is BLOCKED, never PASS.

## Current sandbox limitation

The present verification sandbox may not contain `duckdb`, `sqlglot`, `openai`, Docker, or external credentials. Those checks must be rerun in a clean project environment before production deployment.
