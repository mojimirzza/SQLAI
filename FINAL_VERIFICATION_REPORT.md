# ITXN Stage 4 — Full Verification / Release Readiness Report

**Verification date:** 2026-08-29
**Baseline:** ITXN_STAGE4_MSCHEMA_P0_FINAL.zip
**Verification scope:** Core, M-Schema, SML, Evidence/Hypothesis/Council/Governance, integration boundaries, deterministic regression, golden fixtures, packaging.

## Executive result

The repository passes all verification checks that can be executed in the current sandbox and has a real end-to-end SQLite verification from Query + Alert + Investigation → one Situation → Evidence → Hypotheses → Council → Proposal → Governance.

The full DuckDB/OpenAI runtime could not be executed in this sandbox because the environment does not contain the repository's declared `duckdb`, `sqlglot`, and `openai` packages and outbound package installation is unavailable. Those checks are therefore **BLOCKED BY ENVIRONMENT**, not marked as code PASS.

## Executed checks

| Check | Result | Notes |
|---|---|---|
| Python compileall | PASS | All Python sources compile. |
| Full pytest suite | PASS | 15 passed, 3 skipped. |
| Deterministic golden suite | PASS | 8/8 explicit transaction fixtures. |
| SML three-source E2E | PASS | 3 signals, 2 matches, 1 Situation, 0 errors. |
| Situation → Evidence | PASS | Evidence package accepted. |
| Evidence → Hypothesis | PASS | Evidence-driven candidate hypotheses produced. |
| Hypothesis → Council | PASS | Council produces winner plus arguments/counterarguments. |
| Council → Proposal | PASS | Proposal stored in pending state. |
| Proposal → Governance | PASS | Human approval recorded; second decision rejected. |
| SML idempotency structure | PASS | Composite PK prevents duplicate signal relationships. |
| Core → SML/Evolution import isolation | PASS | No direct imports from these new layers into `src/`. |
| Main API canonical wiring | PASS | `src.api.main` delegates to enriched application. |
| M-Schema tests | PASS | Compiler/context/intent integration tests pass. |
| DuckDB initializer | BLOCKED | `duckdb` package unavailable in sandbox. |
| SQLGlot runtime validation | BLOCKED | `sqlglot` package unavailable in sandbox. |
| OpenAI API runtime | BLOCKED | `openai` package unavailable and no API credentials. |
| Docker build/runtime | BLOCKED | Docker executable unavailable in sandbox. |

## Real E2E evidence

A local SQLite-only verification created three independent source stores and executed the real SML and Evolution code:

```text
Query (src)
   +
Alert (agents)
   +
Investigation (sidecar)
        ↓
Situation Correlator
        ↓
1 Situation / 3 signals / 3 source systems
        ↓
Evidence Package
        ↓
2 evidence-driven hypotheses
        ↓
4-role Council
        ↓
Pending Knowledge Change Proposal
        ↓
Human Governance approval
```

Observed SML run:

```text
signals_seen = 3
matches      = 2
created      = 1
errors       = 0
rule_version = 1.2
```

## Verification fixes made during this pass

### 1. Restored a real deterministic golden corpus

The repository previously had a golden runner that expected a missing fixture file and also inferred intent using English string heuristics. That made the advertised golden suite non-runnable and weak as a regression signal.

The verification pass added:

- `tests/golden/test_transactions.json`
- an explicit-intent version of `scripts/run_golden_tests.py`

The fixture set uses Persian user-facing questions but supplies an explicit canonical intent/entity contract, so failures are attributable to the deterministic SQL generator and semantic layer rather than an untested heuristic parser.

Result:

```text
8/8 passed
```

## Core architecture findings

### Primary path

The main path remains:

```text
User
  ↓
Policy
  ↓
Intent
  ↓
SQL generation
  ↓
Review / validation
  ↓
Execution
  ↓
Baseline
  ↓
CEO + Analyst
  ↓
Return
```

The repository has no direct `sml` or `evolution` imports in `src/`.

### Async boundary

`EnrichedOrchestrator` persists the query record before invoking optional Sidecar hooks and invokes `trigger_suggest_async()` / async investigation. The synchronous `trigger_suggest()` helper remains available as a utility, but is not used by the main response path.

## Remaining release-readiness gaps

These are not hidden:

1. **Full DuckDB runtime verification** requires an environment with the declared dependencies installed.
2. **Full OpenAI/API runtime verification** requires a configured API environment.
3. **Docker build/runtime verification** requires Docker.
4. The repository's production deployment profile still launches the API container; dedicated always-on SML/Evolution workers are not yet modeled as production services. MVP execution remains script-driven.
5. The DuckDB executor accepts a `timeout_ms` argument but the current implementation does not enforce a database statement timeout internally. This should be addressed during production hardening before relying on the parameter as a hard execution-time guarantee.

## Acceptance decision

**Architecture / deterministic integration:** ACCEPTED for progression.

**Full production-runtime certification:** NOT YET CERTIFIED because environment-dependent checks are blocked and the timeout enforcement gap remains.

## Recommended next gate

Proceed to the previously agreed next phase: **environment-complete release verification** with the actual project dependencies and seeded DuckDB/API environment, followed by latency/load and security testing.

No new architectural layer is recommended before that gate.
