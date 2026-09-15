# Baseline vs Agentic Branch — Merge Review

## Compared versions

- **Left / previous baseline:** `ITXN_STAGE4_FINAL_ACCEPTANCE_CANDIDATE.zip`
- **Right / parallel agentic branch:** `ITXN_STAGE4_FINAL_RELEASE_FREEZE_v1_FINAL.zip`
- **Result:** branch changes reviewed and retained selectively in the final freeze.

## High-level delta

| Previous baseline (LEFT) | Agentic branch (RIGHT) | Final |
|---|---|---|
| Sidecar investigation had a bounded batch-style flow | Shared `ReActAgent` drives observation -> next action | **KEEP RIGHT** |
| Investigation state persisted mainly at run level | Per-iteration persistence + audit events | **KEEP RIGHT** |
| No dedicated loop replay helper | `LoopVerifier` + `LoopEvaluator` + `LoopReplay` | **KEEP RIGHT** |
| SML worker used a basic infinite polling loop | Resilient worker with backoff, stop handling and failure isolation | **KEEP RIGHT** |
| SML had no explicit loop trace link | Situation stores references to Sidecar investigation/run/trace/iteration count | **KEEP RIGHT** |
| No read-only historical Situation provider for Sidecar | Bounded, fail-safe `SituationMemoryProvider` + `read_situation_memory` tool | **KEEP RIGHT** |
| SML remained deterministic correlation | Still deterministic correlation; no LLM decision loop added | **KEEP / FREEZE** |
| Main Chain isolation | Same isolation preserved | **KEEP** |

## Representative code-side comparison

### 1. Sidecar loop engine

**LEFT**
```python
for step_num in range(self.max_steps):
    plan = self._plan(messages)
    ...
    obs = self.tools[tool_name].run(**tool_input)
    ...
```

**RIGHT**
```python
for step_num in range(1, self.max_steps + 1):
    plan = self._plan(messages)
    action = plan["action"]
    ...
    state.start_iteration(...)
    ...
    state.finish_iteration(...)
```

**Meaning:** the loop itself is not merely renamed; every iteration is now a durable, auditable state transition.

### 2. Situation Memory access

**LEFT**
```text
Sidecar -> local alert/query context -> investigation
```

**RIGHT**
```text
Sidecar -> SituationMemoryProvider (read-only)
      -> deterministic historical retrieval
      -> evidence_only / decision_binding=false
      -> ReAct may consult memory as a tool
```

**Meaning:** historical operational experience becomes explicit context, but it does not become an instruction source.

### 3. SML worker

**LEFT**
```python
while True:
    result = correlator.run_once()
    time.sleep(interval)
```

**RIGHT**
```python
while not self.stop_requested:
    try:
        result = self.run_once() or {}
        ...
        backoff = self.interval_seconds
    except Exception:
        ...
        backoff = min(self.max_backoff_seconds, backoff * 2)
```

**Meaning:** transient errors no longer kill the SML worker loop; it has bounded backoff and graceful shutdown.

### 4. Situation / investigation trace linkage

**LEFT**
```text
Situation <- signals
```

**RIGHT**
```text
Situation
  <- signals
  <- loop trace refs
       investigation_id
       run_id
       trace_id
       iteration_count
```

**Meaning:** historical Situations can point back to the investigation loop that produced the evidence without copying the action itself into memory.

## New files retained from the branch

- `sidecar/core/loop_engineering.py`
- `sidecar/core/situation_memory.py`
- `sml/core/contracts.py`
- `sml/retrieval.py`
- `sml/worker.py`
- `scripts/replay_investigation.py`
- SML/Sidecar integration and contract tests

## Important rejection

The branch documentation uses the phrase “SML -> ReAct”, but the implementation does **not** make SML itself a ReAct/LLM decision-maker. The final freeze deliberately preserves this distinction:

> **Sidecar is agentic. SML is deterministic, resilient and evidence-only.**

This is the final architectural interpretation used for the release package.
