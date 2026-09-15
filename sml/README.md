# RFC-003 — Situation Memory Layer

SML is an asynchronous consumer over the existing ITXN Core, Agent and Sidecar signals.

It owns only:

- unified `Situation` entities
- cross-system signal relationships
- historical situation memory
- derived pattern-family metadata
- pattern evidence
- deterministic read-only historical retrieval

It never owns SQL execution, alerting, anomaly investigation, semantic contracts, production playbooks, or governance decisions.

## Run

```bash
python -m sml.main --once
python -m sml.main --analyze
```

## Retrieval contract

`SituationMemoryRetriever` consumes a `SituationMemoryRequest` and returns a bounded `SituationMemoryResponse` with `authority="evidence_only"` and `decision_binding=false`.

The retriever is deterministic and read-only. It supplies historical context; the ReAct Agent remains responsible for deciding what to do next.
