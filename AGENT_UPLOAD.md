# Agent Upload Instructions

This is the final reviewed version of the project with SQL Reviewer integration.

## Non-negotiable architecture

- Do not remove existing layers or technology stack.
- Do not make the LLM the executable SQL author.
- SQL must continue to come from the Semantic Layer + deterministic Jinja2 generator.
- SQLGlot remains the validation gate before execution.
- DuckDB executor remains read-only.
- BA and CEO synthesis remains in place.
- RAG/vector, logging, policies, FastAPI, Docker, and tests remain in place.

## SQL Reviewer

The reviewer is a lightweight semantic review step. It uses the same configured OpenAI model through the existing LLM adapter; no new LLM or runtime dependency is required.

Flow:

1. Generate deterministic SQL.
2. Decide whether review is needed based on query complexity.
3. Reviewer returns structured Pydantic-compatible feedback.
4. If approved: continue to SQLGlot validation.
5. If rejected with a safe structured correction: revise intent/entities and regenerate SQL deterministically.
6. Review the regenerated SQL once more.
7. If still rejected: stop safely; do not execute.

The reviewer never returns or executes replacement SQL.

## Test before modifying

```bash
pytest -q
python scripts/run_golden_tests.py
```

Keep the reviewer scope narrow. Do not add parallel per-dimension agents or reflection loops unless measured tests show a clear benefit.
