# SML → ReAct Investigator Integration v1

## Scope

Expose Situation Memory to the Sidecar ReAct investigator without changing the Main Chain and without giving memory decision authority.

## Contract

- SML is read-only from the investigator.
- The provider opens `situation_memory.db` in SQLite read-only mode (`mode=ro`).
- Retrieval is bounded to a configurable maximum of 20 historical Situations; default is 5.
- Returned payload is explicitly `authority=evidence_only` and `decision_binding=false`.
- Historical evidence is serialized as **untrusted historical evidence**. It is not treated as an instruction, playbook, or recommendation.
- Provider initialization, missing DB, corrupted DB, or retrieval errors fail closed to an empty context (`status=bypassed`) and do not fail the investigation.
- SML is available both as initial investigation context and as a bounded ReAct tool (`read_situation_memory`).
- The ReAct agent remains responsible for choosing the next drill-down and must independently validate hypotheses with read-only warehouse tools.

## Pre/Post Safety Checks

The frozen Sidecar `src/` tree is treated as immutable for this integration. A release gate records SHA-256 hashes before and after changes and requires byte-for-byte equality.

## Non-Goals

No synchronous Main Chain → SML dependency, no SML writes, no Council/Governance integration, no automatic action execution from historical memory.
