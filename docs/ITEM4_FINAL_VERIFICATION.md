# ITXN Stage 4 — Item 4 Final Verification

## Baseline before Item 4
- pytest: 32 passed, 3 skipped, 0 failed
- security audit: 0 source-store write violations; 0 core extension imports
- SML performance smoke: p50 0.1240s, p95 0.1663s, p99 0.1701s, mean 0.1386s

## Item 4 changes
- resilient SML worker with graceful shutdown and bounded exponential backoff
- read-only ReAct investigation replay CLI
- SML situation-store health check helper
- non-root production container + API healthcheck
- persistent release data volume shared by API/workers
- no direct SML/Evolution coupling introduced into `src/`

## Verification after Item 4
- pytest: 48 passed, 3 skipped, 0 failed
- Python compileall: PASS
- deterministic aggregate golden: 8/8 PASS
- deterministic Detail/Top-N golden: 2/2 PASS
- pytest: 47 passed, 3 skipped, 0 failed
- security audit: 0 source-store write violations; 0 core extension imports
- SML performance smoke: p50 0.1315s, p95 0.2159s, p99 0.2234s, mean 0.1612s
- replay smoke: PASS
- YAML validation: PASS
- source `src/**/*.py` SHA-256 set: UNCHANGED relative to Item 3 baseline
- release gate: failures=0, blocked=1

## Blocked environment checks
The sandbox does not provide the complete declared runtime stack (`duckdb`, `sqlglot`; the release gate reports its runtime dependency group as BLOCKED) and Docker is unavailable. These are environment blockers, not test failures.

## Acceptance
- Item 4 hardening: **CLOSED / GREEN**
- Full production-runtime certification: **NOT YET CERTIFIED** until the target environment runs dependency-complete DuckDB/SQLGlot/OpenAI/Docker verification.

## Architectural invariant
Memory gives evidence; ReAct decides; Governance controls. SML remains asynchronous/read-only/evidence-only and must not affect primary user-query availability.
