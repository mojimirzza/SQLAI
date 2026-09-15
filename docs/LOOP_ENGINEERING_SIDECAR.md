# Sidecar Loop Engineering — v1

## Purpose

This change turns the existing Sidecar ReAct capability into an auditable loop for anomaly investigation without touching `src/` or production data stores.

## Runtime contract

For each investigation run:

```text
Goal / Task
   ↓
Decide one next action
   ↓
Act (read-only tool)
   ↓
Observe tool result
   ↓
Verify execution result
   ↓
Persist iteration
   ↓
Decide again
   ↺
Finish / Max-step stop
```

The investigator is now driven by the shared `sidecar/core/agent.py` ReAct engine. It does not pre-generate a batch of drill-downs and blindly execute them.

## State contract

`agent_state.db` keeps the existing tables and adds two append-oriented loop tables:

### `agent_iterations`

One row per loop iteration:

- `iteration_id`
- `run_id`
- `investigation_id`
- `iteration_no`
- `started_at`, `finished_at`
- `decision_action`
- `action_input_json`
- `observation_json`
- `action_status`
- `verification_status`, `verification_reason`
- `retry_count`
- `termination_reason`

### `loop_events`

An append-only audit stream for decision/observation events. This makes a run reconstructable without exposing model private reasoning as durable state.

## Guardrails

- Only registered tools can be selected.
- Investigation warehouse access stays read-only and passes through `SidecarSQLGuard`.
- Drill-down query budget remains bounded by `max_drilldown_queries`.
- Loop steps remain bounded by `max_steps` (default 10).
- No write path is added to `memory.db`, warehouse, or `agent_alerts.db`.

## Verification

Each tool action receives execution-level verification:

- `passed`: tool returned `status=ok`
- `failed`: tool returned an error or was not registered

Structural verification is available through `LoopVerifier`.

## Evaluation

`LoopEvaluator` scores the trace using execution verification coverage, action diversity, and error penalty. This is a CI-oriented structural score, not a claim of business correctness.

## Replay

`LoopReplay` reconstructs the recorded iteration sequence without calling the LLM or executing tools. This is an audit/review replay, not a fresh live re-execution of external systems.

## Files changed

- `sidecar/core/agent.py` — persistent per-iteration loop hooks and terminal reasons
- `sidecar/core/state_manager.py` — iteration/event persistence, status update
- `sidecar/core/loop_engineering.py` — verifier, evaluator, replay utilities
- `sidecar/agents/anomaly_investigator.py` — investigator now uses ReAct engine
- `sidecar/main.py` / `sidecar/config.yaml` — configurable investigation max steps
- `sidecar/tests_stage4.py` — contract and adaptive-action tests

## Acceptance criteria

The implementation is accepted when CI proves:

1. Iteration IDs and ordering are preserved.
2. Every action is linked to an iteration.
3. Tool observations are persisted.
4. Execution verification is persisted.
5. Finish and max-step termination are explicit.
6. A later decision can differ from the prior action based on observation.
7. Existing Sidecar tests remain green.

## Scope boundary

This is intentionally a Sidecar-only evolution. The main Text-to-SQL path remains unchanged. Situation Memory is the next consumer of these lessons; it is not modified by this change.
