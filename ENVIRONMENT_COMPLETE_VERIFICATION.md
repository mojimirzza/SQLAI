# ITXN Stage 4 — Environment-Complete Verification Report

## Scope

This stage verifies the Release Candidate repository as far as the available execution environment permits, covering:

- Python compilation
- full pytest regression suite
- deterministic golden corpus
- SML end-to-end and performance smoke
- security static audit
- Core/SML/Evolution isolation
- canonical API entrypoint
- Docker Compose syntax
- release-gate correctness
- environment dependency readiness

## Results

| Check | Result | Evidence |
|---|---|---|
| Python compileall | PASS | `python -m compileall -q .` |
| Pytest | PASS | `23 passed, 3 skipped` |
| Golden corpus | PASS | `8/8 passed` |
| Security audit | PASS | `0` source-store write violations; `0` forbidden Core extension imports |
| SML performance smoke | PASS | 500 signals/run; p50 0.5242s, p95 0.5962s, p99 0.5996s in latest run |
| Canonical API wiring | PASS | `src.api.main` delegates to `main_enriched` |
| Core isolation | PASS | no SML/Evolution imports under `src/` |
| Compose YAML syntax | PASS | both compose files parse successfully |
| Clean source tree | PASS | release gate removes/validates bytecode/cache artifacts |
| Runtime dependency preflight | BLOCKED | sandbox lacks `duckdb`, `sqlglot`, `openai` |
| Docker execution | BLOCKED | Docker executable unavailable in sandbox |

## Important Gate Correction

The previous release verification wrapper could report PASS while an environment check was BLOCKED. That is now corrected.

Current behavior:

```text
FAIL    -> release verification fails
BLOCKED -> release verification fails
PASS    -> only when all required checks pass
```

Therefore a real environment cannot accidentally receive a false-green verification result.

## Runtime Dependency Reproduction

The declared dependencies are present in `requirements.txt`:

- duckdb
- sqlglot
- openai

Import probing in this sandbox reports them as unavailable. Attempting installation failed because the environment has no network/DNS access.

This is therefore an environment limitation for this verification run, not evidence that the repository dependency declarations are incorrect.

## Docker Reproduction

The sandbox does not contain the Docker executable, so these checks cannot honestly be marked PASS here:

```bash
docker compose -f docker-compose.release.yml config
docker compose -f docker-compose.release.yml build
docker compose -f docker-compose.release.yml up
```

The Compose YAML itself parses successfully.

## Acceptance Position

Repository-level release hardening is complete.

Environment-complete certification remains **BLOCKED**, not failed, until a machine with the declared runtime dependencies and Docker executes the final gate.

## Exact Final Command

From the repository root:

```bash
python -m pip install -r requirements.txt
python scripts/run_full_verification.py
docker compose -f docker-compose.release.yml build
docker compose -f docker-compose.release.yml up
```

The expected final state is:

```text
SUMMARY: failures=0, blocked=0
FULL VERIFICATION: PASS
```

Only after that result should the project be called environment-verified.


## Additional Release-Gate Hardening

The deterministic SML performance smoke test is bounded to 3 runs of 100
signals and each release-gate subprocess has a 30-second timeout. A hung
verification step therefore becomes an explicit FAIL rather than hanging the
release process indefinitely.
