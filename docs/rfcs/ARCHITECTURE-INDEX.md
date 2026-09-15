# ITXN Architecture Index

## RFC-004 — Core

The fast, deterministic analytical system: understand → model → serve.

## RFC-003 — Situation Memory

Asynchronous cross-system operational memory over existing query, alert, and investigation signals.

## RFC-001 — Evidence and Council

Governed reasoning over traceable evidence. Produces hypotheses and change proposals; it does not directly mutate production.

## Dependency direction

```text
RFC-004 Core
    ↓ signals/state
RFC-003 Situation Memory
    ↓ evidence
RFC-001 Evidence / Hypothesis / Council
    ↓ proposal
Governance
```

The primary query path never depends on RFC-003 or RFC-001.
