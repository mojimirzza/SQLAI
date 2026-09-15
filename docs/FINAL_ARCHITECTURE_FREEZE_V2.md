# ITXN Stage 4 — Final Architecture Freeze v3

Date: 2026-09-06

## Final decision

**FINAL RELEASE CANDIDATE — ARCHITECTURE FROZEN**

This revision keeps the valuable agentic-loop work from the parallel branch while preserving the existing Main Chain and governance boundaries, while adding the bounded deterministic Detail/Top-N query-shape contract required for forensic transaction analysis.

### Frozen architecture

```text
USER
  |
  v
CORE / MAIN CHAIN (fast, deterministic)
  |
  +--> CEO + Analyst response
  |
  +--> async trigger boundary
          |
          v
     SIDECAR ReAct LOOP
       |  bounded steps / tool budget
       |  persisted iterations / observations
       |  verification / retry metadata
       |  replay / audit
       v
     EVIDENCE / INVESTIGATION
       |
       v
     SITUATION MEMORY (SML)
       |  deterministic correlation
       |  historical retrieval
       |  resilient worker loop
       |  evidence-only contract
       v
     RFC-001 EVIDENCE PACKAGE
       |
       v
     HYPOTHESIS -> COUNCIL -> GOVERNANCE
```

## Keep / Refactor / Reject

| Area | Decision | Final treatment |
|---|---|---|
| Main `src/` query path | EXTEND, backward-compatible | Aggregate path remains compatible; Intent/SQL generation gains explicit Detail/Top-N query shape support. |
| Sidecar ReAct loop | KEEP | Retained as the real agentic investigation loop. |
| Loop state / replay / audit | KEEP | Persisted iterations, loop events, verification and replay retained. |
| Situation Memory deterministic correlation | KEEP | Remains the source of historical situation evidence. |
| SML resilient worker | KEEP | Failure-isolated periodic processing with bounded backoff and graceful stop. |
| SML -> Sidecar memory access | KEEP | Read-only, bounded, fail-safe, explicitly non-binding. |
| LLM/ReAct inside SML | REJECT for this freeze | Not required to make SML useful; would add an unnecessary decision loop. |
| Autonomous playbook/governance mutation | REJECT | Governance remains the authority. |
| Durable event/outbox | REFACTOR / NEXT | Not introduced into the freeze because the current branch uses a process-level async boundary. |

## Loop contract

### Sidecar
- One decision per iteration.
- Each tool action is independently guarded and read-only.
- `max_steps` bounds the reasoning loop.
- `max_drilldown` bounds warehouse access.
- Each iteration persists action, reason, input, observation, action status, verification, retry count and termination reason.
- A replay utility reconstructs the trace without calling the LLM or executing tools.

### SML
- Correlation is deterministic.
- The worker is resilient but does not make operational decisions.
- Historical retrieval is bounded and read-only.
- SML output is `authority=evidence_only` and `decision_binding=false`.
- Historical evidence is explicitly treated as untrusted context.

## Primary-path invariant

No `src/` module imports SML or Evolution. SML and Sidecar remain outside the synchronous analytical request/response path.

## Verification snapshot

Executed in the available sandbox on 2026-09-05:

- `pytest -q`: **47 passed, 3 skipped**
- Python compileall: **PASS**
- Aggregate golden suite: **8/8 PASS**
- Detail/Top-N golden suite: **2/2 PASS**
- Security static audit: **PASS**
- SML performance smoke: **PASS**
- Release-candidate gate: **0 failures, 1 environment block**

The only release-gate block is environment/runtime completeness: `duckdb`, `sqlglot`, `openai` and Docker are unavailable in the sandbox. This is intentionally reported as **BLOCKED**, not PASS.

## Detail / Top-N contract

Core now supports four explicit query shapes: `aggregate`, `detail`, `top_n_detail`, and `top_n_aggregate`. Business metrics and result shape are separate concerns. Detail fields and joins are allow-listed by `semantic_layer.yaml`; the generator never falls back to guessing detail SQL. `TOP_N_DETAIL` requires a bounded limit and a semantic order field and cannot emit aggregate functions or `GROUP BY`.

The authoritative schema currently contains no customer dimension/key. Customer-level forensic requests therefore remain unsupported until such a dimension is added to the semantic layer.
