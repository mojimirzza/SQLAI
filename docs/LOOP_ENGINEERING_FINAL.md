# Sidecar Loop Engineering v1.1 — Finalization Record

Status: FINAL / FROZEN

Scope: sidecar only. The main `src/` analytical path is intentionally untouched.

## Final behavior

- `AnomalyInvestigator` uses the shared `ReActAgent` engine.
- Each iteration persists decision action + decision reason + action input.
- Each iteration persists observation, action status, verification status/reason, retry count, and termination reason.
- `agent_runs` retains run-level trace metadata.
- `loop_events` provides an append-only audit stream for decision/observation events.
- `LoopVerifier` checks structural invariants.
- `LoopEvaluator` provides a lightweight CI-facing quality score.
- `LoopReplay` reconstructs the recorded trace without executing tools or calling the LLM; it is trace replay, not a fresh live re-execution.
- Warehouse access remains read-only and SQL-guarded.
- Drill-downs remain bounded by `max_drilldown`; the agent loop remains bounded by `max_steps`.
- Existing `agent_state.db` deployments receive `decision_reason` through a backward-compatible additive migration.

## Explicit non-goals

- No Situation Memory is added here.
- No Governance/Council behavior is added here.
- No changes are made to the main `src/` query-serving path.

## Verification

`pytest -q` => **23 passed, 3 skipped, 0 failed**.

This package is the frozen Sidecar Loop Engineering baseline for the next phase: Situation Memory.
