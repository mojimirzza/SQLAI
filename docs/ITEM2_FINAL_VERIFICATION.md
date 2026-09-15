# Option 2 — SML Retrieval → ReAct Investigator

## Status
CLOSED / GREEN

## Change
Situation Memory is now exposed to the Sidecar ReAct Investigator through a dedicated fail-safe provider.

### Runtime path
1. Investigator starts with the current `query_id`, `investigation_id`, and normalized entities.
2. Provider opens `situation_memory.db` strictly read-only and performs bounded deterministic retrieval.
3. Historical Situations are injected into the ReAct task as explicitly untrusted, evidence-only context.
4. The same bounded retrieval is also available as a ReAct tool named `read_situation_memory` for later iterations.
5. ReAct still decides the next action; warehouse drill-down remains independently guarded and read-only.
6. Missing/corrupt/unavailable SML causes `status=bypassed` and an empty evidence set; investigation continues.

## Safety invariants
- `authority = evidence_only`
- `decision_binding = false`
- Retrieval limit is configurable and hard-clamped to 20.
- No SML write is performed by the Sidecar integration.
- No historical `action`/`next_action` instruction is surfaced as executable guidance.
- Main Chain `src/` is byte-for-byte unchanged from the frozen Sidecar baseline.

## Before / After Verification
- Frozen Sidecar baseline was used as the integration base.
- Hardened SML P0 baseline was layered in without replacing the frozen Sidecar loop engine.
- `src/` SHA-256 manifest: 33 files before / 33 files after; equality confirmed.
- Python compile check: passed.
- Full pytest suite: **31 passed, 3 skipped, 0 failed**.
- New integration tests cover read-only retrieval, bounded retrieval, failure bypass, evidence-only semantics, and ReAct wiring.

## Environment limitation
This verification is structural/unit-level. Full live-investigation execution still depends on the deployment environment providing the project's runtime dependencies (e.g. DuckDB/OpenAI/sqlglot) and real operational databases.
