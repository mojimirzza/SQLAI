# Ultimate Text-to-SQL Dual-Persona v2.1 — Transaction Monitoring

A safer, simple Text-to-SQL pipeline for payment/transaction star schema analytics.

## Pipeline

1. Intent extraction / planning with OpenAI
2. Context building and optional RAG
3. Semantic-layer metric resolution
4. Deterministic SQL generation with Jinja2
5. SQL Reviewer semantic gate (same OpenAI model; no new model/library)
6. Optional single deterministic regeneration from structured reviewer feedback
7. SQLGlot AST validation
8. Read-only DuckDB execution
9. Operations Analyst + Executive synthesis with OpenAI
10. JSON trace logging
11. Policy enforcement
12. FastAPI API
13. Golden + unit tests
14. Docker

## Schema

Kimball-style star schema with 6 dimension tables and 1 fact table:

- **fact_transaction** — central fact with measures (txnamt, latency, flags)
- **dim_date** — YYYYMMDD integer SK
- **dim_time** — seconds-since-midnight integer SK (0-86399)
- **dim_server** — server_name, server_type, location
- **dim_terminal** — device_category, entry_mode, risk_score
- **dim_status** — status_code, lifecycle_stage, flags
- **dim_error** — err_severity, error_description

## Important design rule

The LLM does **not** author executable SQL. The reviewer also does not author SQL.
The reviewer only checks the generated SQL and, when needed, proposes structured
corrections to intent/entities. The deterministic SQL generator then rebuilds SQL
from the semantic layer.

## Run locally (quick start)

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # add your OPENAI_API_KEY
python scripts/init_db.py
python run.py              # canonical enriched API; or: PYTHONPATH=src uvicorn src.api.main:app --reload
```

## Run with Docker

```bash
cp .env.example .env        # add your OPENAI_API_KEY
docker-compose up --build
```

## Test

```bash
pytest -q
python scripts/run_golden_tests.py
python scripts/run_detail_golden_tests.py
```

## API

POST `/query`

```json
{"text":"What was the average switch latency for Server A yesterday?"}
```

For production, replace the DuckDB and in-memory vector adapters through the existing ports.

## Architecture Extensions

This repository now includes the three agreed architecture RFCs under `docs/rfcs/`.

- `RFC-004`: Core Text2SQL baseline and ownership boundaries
- `RFC-003`: asynchronous Situation Memory
- `RFC-001`: Evidence → Hypothesis → Council → governed proposal

The primary `User → CEO/Analyst Response` path does not wait for the new learning layers.

### Run Situation Memory once

```bash
python -m sml.main --once
```

### Analyze Situation patterns

```bash
python -m sml.main --analyze
```

### Run the Evidence → Council loop

```bash
python -m evolution.main --situation-id <SITUATION_ID>
```

## Mobile Lab

For browser-only testing, see `MOBILE_LAB.md`. The mobile lab adds a one-input browser UI and a current-date demo seed. It also fixes the alert agent's DuckDB/SQLite mismatch.
