# RFC-001 — Evidence / Hypothesis / Council

This package implements the v1 governed reasoning path after RFC-003 Situation Memory.

```text
Situation / Pattern
      -> Evidence Package
      -> Hypotheses
      -> Council scoring/debate
      -> Knowledge Change Proposal
      -> Human Governance
```

The implementation is intentionally safe by default:

- evidence is traceable to source signals;
- hypotheses are explicit and not treated as facts;
- Council produces a recommendation, not a production mutation;
- proposals remain `pending` until a human governance action approves or rejects them.

Run for a situation:

```bash
python -m evolution.main --situation-id <SITUATION_ID>
```
