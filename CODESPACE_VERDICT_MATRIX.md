# Full-System Verdict Matrix

| Layer | Runtime surface | Dependency | Expected verdict |
|---|---|---|---|
| Star Schema | DuckDB + semantic YAML + M-Schema | duckdb | PASS after setup |
| Text-to-SQL | Intent → Context → Jinja SQL → Reviewer → SQLGlot → DuckDB | openai/openrouter, sqlglot, duckdb | PASS with live LLM |
| Alerts | baseline observer → objective engine → alert log | duckdb | PASS without LLM |
| Sidecar | follow-up + ReAct investigation + state | openrouter + sqlite + duckdb | PASS with live LLM |
| SML | query/alert/investigation correlation | sqlite | PASS without LLM |
| Evidence | traceable package + hash | sqlite | PASS without LLM |
| Hypothesis | deterministic candidate generation | sqlite | PASS without LLM |
| Council | evidence-weighted voting | sqlite | PASS without LLM |
| Governance | proposal + human decision gate | sqlite | PASS; never auto-approves |
| Observability | trace logs + state stores | filesystem/sqlite | PASS |
| Mobile access | FastAPI on :8000 + Codespaces port forwarding | Codespaces | PASS |

## What `--live` proves

One real question is sent through the live LLM route. The returned trace is then
used to verify memory persistence and downstream Sidecar activity. The same
Codespace executes the alert, SML, Evidence, Council, and Governance stages.

A `BLOCKED` result is not converted to PASS. A Governance proposal remains
human-gated by design.
