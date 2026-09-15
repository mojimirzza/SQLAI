# ITXN Stage 4 — Item 3: SML → ReAct A/B Evaluation

## Purpose

Measure whether Situation Memory provides useful investigation context beyond the same ReAct loop without historical memory, while preserving the evidence-only boundary.

## Experimental design

Two arms are compared on five deterministic banking-monitoring scenarios:

- **Treatment / Memory:** historical Situation evidence is injected before the ReAct loop.
- **Control / No Memory:** the same task and tool are used without historical Situation context.

The treatment difference is only the presence of SML evidence. The scenarios contain a historical recurring server that matches the current anomaly. The planner must independently validate that lead with a read-only warehouse action.

## Metrics

- success rate
- target-hit rate
- targeted-first rate
- mean drill-down count
- delta in targeted-first percentage points

## Safety gates

- no production DB or LLM calls
- SML provider remains evidence-only and read-only
- historical memory is explicitly untrusted context
- no action from memory is executed directly
- Main Chain remains out of the experiment

## Result

Executed in the isolated repository environment:

| Metric | Memory | Control | Delta |
|---|---:|---:|---:|
| Success rate | 100% | 100% | 0 pp |
| Target-hit rate | 100% | 100% | 0 pp |
| Targeted-first rate | 100% | 0% | +100 pp |
| Mean drill-downs | 1.00 | 2.00 | -1.00 |

The deterministic gate is **PASS**. The treatment arm reaches the known target with one drill-down on average, while the control arm requires two.

This is a **synthetic deterministic A/B gate**. It validates the integration mechanism and expected directional benefit; it is not a claim about real LLM quality, human analyst accuracy, or production capacity.

## Production / target-environment follow-up

A production-grade evaluation should replay a blinded corpus of real investigations with human adjudication and compare hypothesis accuracy, time-to-correct-hypothesis, unnecessary drill-downs, false correlations, and safety violations. That requires the declared DuckDB/OpenAI environment and a labelled corpus.
