# ITXN Stage 4 — Release Candidate Verification Report

**Baseline:** ITXN_STAGE4_MSCHEMA_VERIFIED_v2
**Gate:** Release Candidate Hardening

## Executive result

Repository-level verification is green. Environment-dependent runtime certification is still blocked in this sandbox because `duckdb` and `sqlglot` are not installed and Docker is unavailable. This report does not convert those blocked checks into PASS.

## Executed checks

| Check | Result |
|---|---|
| Python compileall | PASS |
| Full pytest suite | PASS — 53 passed, 3 skipped |
| Deterministic aggregate golden suite | PASS — 8/8 |
| Deterministic Detail/Top-N golden suite | PASS — 2/2 |
| Canonical API entrypoint | PASS |
| Core isolation from SML/Evolution | PASS |
| SML normalization runtime smoke | PASS |
| Source tree cache cleanup | PASS |
| DuckDB initializer | BLOCKED — dependency unavailable |
| M-Schema compilation against real DuckDB | BLOCKED — seeded DB/dependency unavailable |
| SQLGlot runtime validation | BLOCKED — dependency unavailable |
| OpenAI API runtime | BLOCKED — credentials/environment unavailable |
| Docker build/runtime | BLOCKED — Docker unavailable |

## Hardening implemented in this gate

### Query timeout

`DuckDBExecutor.execute(..., timeout_ms=...)` now has a real watchdog using a daemon timer and DuckDB connection interrupt. A timed-out execution returns a failed `ExecutionResult` with an explicit timeout error.

### Release gate

`scripts/run_release_gate.py` is a repeatable repository gate. It runs compile, pytest, golden regression, canonical entrypoint checks, Core isolation checks, dependency detection, and source-tree cleanup. Missing environment dependencies are reported as BLOCKED.

### Documentation consistency

- Sidecar documentation now describes follow-up suggestions as asynchronous persistence rather than promising them synchronously in the primary response.
- RFC-004 readiness language reflects the current async hardening and 8-question canonical golden corpus.
- `docs/RELEASE_CANDIDATE.md` records the acceptance gates and remaining environment-specific checks.

## Architectural acceptance

The following invariants remain intact:

```text
User
 ↓
Core / RFC-004
 ↓
CEO + Analyst
 ↓
RETURN

================ ASYNC BOUNDARY ================

SML / RFC-003
 ↓
Evidence / RFC-001
 ↓
Council
 ↓
Governance
```

No SML or Evolution dependency is introduced into the primary `src/` request path.

## Remaining Go/No-Go blockers

Before production certification, run the same repository gate in a clean project environment with:

- the declared dependency set installed;
- a successfully initialized seeded DuckDB;
- SQLGlot runtime validation enabled;
- actual OpenAI configuration for end-to-end LLM stages;
- Docker available for image build/startup;
- deployment-scale latency, concurrency, and security testing.

## Decision

**Release-candidate repository hardening: ACCEPTED.**

Detail/Top-N extension verification is green at the repository level; environment-complete runtime certification remains pending.

**Production certification: NOT YET CERTIFIED.**

No additional architectural layer is required at this stage. The next activity is environment-complete verification and measurable performance/security acceptance.
