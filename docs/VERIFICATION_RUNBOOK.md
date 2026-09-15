# ITXN Stage 4 — Verification Runbook

This runbook is the operational gate after repository-level Release Candidate hardening.

## 1. Clean environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Repository gate

```bash
python scripts/run_release_gate.py
```

Expected hard-failure count: `0`.

## 3. Seed the analytical database

```bash
python scripts/init_db.py
```

This must succeed before runtime certification.

## 4. M-Schema refresh

```bash
python scripts/mschema_compiler.py
```

Verify that the generated artifact contains the expected analytical tables, relationships, and only approved sample values.

## 5. Golden regression

```bash
python scripts/run_golden_tests.py
python scripts/run_detail_golden_tests.py
```

Expected: aggregate `8/8 passed`; Detail/Top-N `2/2 passed`.

## 6. API health

Start:

```bash
python run.py
```

Then verify:

```bash
curl -fsS http://localhost:8000/health
```

## 7. User-path E2E

Execute representative queries and confirm:

`Question → Intent → SQL → Review → Validation → Execute → Baseline → CEO/Analyst → Return`

No SML, Evolution, or Governance call is awaited by this path.

## 8. SML E2E

Seed query, alert, and investigation records, then:

```bash
python -m sml.main --once
```

Verify one Situation contains all three source systems.

## 9. Evolution E2E

```bash
python -m evolution.main --situation-id <SITUATION_ID>
```

Verify:

`Situation → Evidence → Hypothesis → Council → Proposal`

Then verify the governance decision is persisted.

## 10. Performance

```bash
python scripts/run_performance_smoke.py
```

This is a deterministic SML smoke benchmark. Production certification also requires measured Core p50/p95/p99 under representative concurrency.

## 11. Security

```bash
python scripts/run_security_audit.py
```

The audit must report zero source-store write violations and zero forbidden Core imports.

## 12. Deployment

For a deployment environment with Docker:

```bash
docker compose -f docker-compose.release.yml build
docker compose -f docker-compose.release.yml up -d api agents sml-worker
docker compose -f docker-compose.release.yml ps
```

Then validate `/health`, logs, worker execution, and clean shutdown/restart.

## Go / No-Go

GO requires all repository checks green plus all environment-dependent checks executed successfully in the target environment. Missing credentials, unavailable Docker, or missing runtime dependencies are `BLOCKED`, not `PASS`.
