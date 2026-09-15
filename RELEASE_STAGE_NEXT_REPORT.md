# ITXN Stage 4 — Release Hardening / Verification Report

## Status

**Repository-level gate: PASS**

**Item 3 A/B evaluation: PASS**

**Production/environment certification: BLOCKED until run in a clean target environment with declared runtime dependencies, Docker and real credentials/data sources.**

## Work completed

- Preserved the existing Core ownership boundaries.
- Preserved the synchronous user path: Query → Core → CEO/Analyst → Return.
- Added an operational SML loop mode (`python -m sml.main --loop --interval-seconds N`).
- Added a release deployment compose file with API, Agent, SML worker, and Sidecar report service definitions.
- Added a full verification wrapper and a security audit script.
- Added deterministic SML performance smoke benchmarking with p50/p95/p99.
- Added release-readiness runbook and deployment instructions.

## Automated results in this sandbox

| Check | Result |
|---|---|
| pytest | 21 passed, 3 skipped |
| Python compileall | PASS |
| Golden corpus | 8/8 PASS |
| Static security audit | PASS (0 source-store write violations, 0 Core extension imports) |
| SML three-source E2E | PASS in test suite |
| SML idempotency | PASS in test suite |
| SML performance smoke | PASS |
| p50 SML run (500 signals) | ~0.71 s |
| p95 SML run (500 signals) | ~0.86 s |
| p99 SML run (500 signals) | ~0.88 s |
| Runtime deps in sandbox | BLOCKED: duckdb, sqlglot, openai unavailable |
| Docker runtime | BLOCKED: target Docker environment unavailable for this run |

## Important interpretation

The SML benchmark is a repository-level deterministic smoke benchmark. It is not a production capacity guarantee. Production performance must be measured against representative data, concurrency, storage, and deployment topology.

The three skipped tests are environment-dependent checks; they are not counted as PASS and are not treated as code failures.

## Target-environment acceptance checklist

- [ ] Clean venv with `requirements.txt` installed.
- [ ] `scripts/init_db.py` succeeds.
- [ ] Canonical `/health` succeeds.
- [ ] At least one real seeded SQL query succeeds end-to-end.
- [ ] Eight golden tests pass.
- [ ] M-Schema compiler runs against the real DuckDB.
- [ ] Three-source SML convergence succeeds on real operational records.
- [ ] Evidence → Hypothesis → Council → Governance succeeds end-to-end.
- [ ] Docker image builds and services start from `docker-compose.release.yml`.
- [ ] Core p50/p95/p99 measured under representative concurrency.
- [ ] Timeout enforcement measured against an intentionally long-running query.
- [ ] Security regression executed with the target configuration.
- [ ] Final Go/No-Go approved by the deployment owner.


## Item 3 A/B Evaluation
- Deterministic treatment/control comparison: PASS.
- Memory arm: 100% success, 100% target-hit, 100% targeted-first, 1.00 mean drill-downs.
- Control arm: 100% success, 100% target-hit, 0% targeted-first, 2.00 mean drill-downs.
- Directional effect: one fewer average drill-down and +100 percentage points targeted-first.
- This remains a synthetic CI gate, not production LLM-quality certification.
