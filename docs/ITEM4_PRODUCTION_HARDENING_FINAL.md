# ITXN Stage 4 — Item 4: Replay, Observability & Production Hardening

## Scope
This gate hardens the current Item 3 baseline without introducing another architectural layer.

## Changes
- SML loop now runs behind a resilient worker boundary with graceful SIGTERM/SIGINT shutdown, exponential backoff on cycle failure, and structured cycle/stop logs.
- Added read-only investigation replay CLI using persisted Sidecar loop traces; replay executes no tools and makes no LLM call.
- Added a lightweight SML situation-store health check.
- Hardened release container to run as non-root and added API healthcheck.
- Added persistent shared data volume to release compose so API/agents/SML/sidecar share the intended data store across container restarts.
- Existing evidence-only SML → ReAct contract remains unchanged.
- `src/` is not modified by this item.

## Verification policy
Code failures are FAIL. Environment limitations are BLOCKED. No BLOCKED check is re-labeled PASS.

## Next gate
Environment-complete deployment verification (DuckDB/SQLGlot/OpenAI/Docker where available), then final release freeze.
