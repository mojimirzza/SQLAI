# ITXN Stage 4 — Release Candidate Hardening

## Purpose

This document defines the release-candidate gate after P0 hardening and the M-Schema integration.
It is intentionally separate from the Core architecture RFCs: it records operational readiness work,
verification boundaries, and the conditions under which the repository may advance toward deployment.

## Canonical architecture

```text
PACKAGE 1 — UNDERSTAND
        ↓
PACKAGE 2 — MODEL
        ↓
PACKAGE 3 — SERVE
        │
        ├── src/      → primary user answer
        ├── agents/   → KPI monitoring
        └── sidecar/ → investigation
                 │
             ASYNC BOUNDARY
                 ↓
             RFC-003 SML
                 ↓
            Pattern Evidence
                 ↓
             RFC-001
       Evidence / Hypothesis / Council
                 ↓
             Governance
```

## Release-candidate work completed in this repository

- Canonical API entrypoint delegates to the enriched Core.
- Follow-up suggestion dispatch is fire-and-forget from the primary path.
- SML is isolated from the synchronous Core path.
- RFC-003 supports multi-signal Situations, audit events, edges, idempotency, and pattern lifecycle.
- RFC-001 stores Evidence, Hypotheses, Council arguments/votes, Proposals, and Governance decisions.
- M-Schema is a build-time context artifact and does not introspect the database per user request.
- DuckDB executor now enforces its `timeout_ms` contract with a watchdog/interrupt mechanism.
- Deterministic golden corpus contains eight canonical business questions.
- `scripts/run_release_gate.py` provides a repeatable repository verification gate.

## Verification layers

### Layer A — Repository checks

These must be green in every environment:

- Python compileall
- pytest
- deterministic golden suite
- canonical API entrypoint
- Core isolation
- clean source tree

### Layer B — Runtime checks

These require the declared project dependencies:

- DuckDB initialization
- SQLGlot validation
- FastAPI health
- seeded database execution
- M-Schema compilation against the real DuckDB

### Layer C — External integration checks

These require deployment infrastructure and/or credentials:

- OpenAI API call
- Docker image build and startup
- actual production database connectivity
- external identity provider
- notifier integrations

### Layer D — Performance/security checks

Before external production deployment, validate:

- primary query latency p50/p95/p99
- query timeout enforcement
- concurrency behavior
- SML throughput and backlog
- retry/idempotency behavior
- SQL injection/policy bypass tests
- authorization boundaries
- sensitive-data redaction in M-Schema and evidence

## Go / No-Go rule

A release candidate is **NO-GO** when any of the following is true:

- the primary user path depends synchronously on SML/Evolution/Council;
- SQL execution can bypass deterministic validation;
- the Core cannot start with the declared dependency set;
- a failing SML/Evolution path can fail a successful user query;
- a production-mutating path bypasses governance;
- a test is claimed PASS without successful execution evidence.

A release candidate may advance with environment-specific checks marked BLOCKED only when those checks
are explicitly assigned to a real deployment environment and are run there before production rollout.

## Next gate

The next gate is **environment-complete verification**, not another architectural layer:

1. Install the declared dependencies in a clean environment.
2. Build and seed the DuckDB database.
3. Run the canonical API and health test.
4. Run the eight golden questions.
5. Run real SML against the seeded operational stores.
6. Run the complete Situation → Evidence → Hypothesis → Council → Governance chain.
7. Measure latency and concurrency.
8. Execute security regression tests.
9. Produce a signed Go/No-Go report.
