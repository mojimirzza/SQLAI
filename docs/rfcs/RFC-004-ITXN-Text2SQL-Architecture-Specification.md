# RFC-004 — ITXN Text2SQL Ultimate Architecture Specification

**Version:** 5.1-FINAL  
**Status:** Architecture Baseline / Source of Truth  
**Date:** 2026-08-26  
**Scope:** Stage 4 codebase and the three-package ITXN analytics architecture  
**Basis:** Stage 4 source archive + existing architecture/stage reports

---

## 1. Purpose

This RFC is the canonical architectural description of the current ITXN Text2SQL system. It documents what exists, what each subsystem owns, the exact safety boundaries, and the interfaces on which the next architectural layer (RFC-003 Situation Memory and RFC-001 Evidence Package) may safely depend.

The document intentionally distinguishes:

```text
IMPLEMENTED NOW
vs
TARGET / FUTURE
```

No future capability is presented as an existing implementation.

---

# 2. Executive Architecture

The platform consists of three primary cooperating runtime subsystems built on three analytical packages:

```text
Package 1 — UNDERSTAND
    Domain dictionary
    Transaction lifecycle
    Domain semantics
        ↓
Package 2 — MODEL
    Facts
    Dimensions
    Marts
    KPI / baseline / DQ layer
        ↓
Package 3 — SERVE
    Text2SQL API
    Agents
    Sidecar
```

The central design principle is:

> **The LLM translates language into structured intent; deterministic components render, validate, execute, and explain SQL.**

The LLM is never the owner of executable SQL generation.

---

# 3. Architectural Non-Negotiables

## 3.1 LLM boundary

The LLM may:

- extract structured intent
- review generated SQL
- synthesize analyst/CEO narratives
- synthesize Sidecar investigation hypotheses

The LLM must not be the authoritative generator of executable SQL.

## 3.2 Semantic authority

`semantic_layer.yaml` defines metric expressions, allowed sources, dimensions, filters, and joins used by deterministic SQL generation.

## 3.3 Safety authority

Generated SQL must pass the canonical SQL validation layer before execution.

## 3.4 Read-only analytics

The application and Sidecar execute analytical reads only. Destructive SQL is rejected.

## 3.5 Domain correctness

Business meaning is defined by Package 1 and the semantic layer, not inferred ad hoc by agents.

## 3.6 Main-path isolation

The primary user response must not depend on future learning systems such as RFC-003 or the Knowledge Council.

---

# 4. Package 1 — UNDERSTAND

## 4.1 Source

Primary operational source:

```text
informix.itxn
```

Domain analysis covers the full 117-column structure.

## 4.2 Core domain model

The architecture captures:

- 12 functional column groups
- 6-step transaction lifecycle
- 8 latency clocks
- three money worlds
- fee waterfall
- outcome taxonomy
- reversal linkage
- DQ red flags

The six-step lifecycle is modeled as:

```text
request
  → route
  → authorize
  → capture
  → settle
  → reverse
```

## 4.3 Authoritative artifacts

- `01_ITXN_Column_Dictionary.md`
- `02_Transaction_Lifecycle_and_Domain_Model.md`
- `itxn_column_dictionary.csv`

These artifacts are domain context for downstream systems.

---

# 5. Package 2 — MODEL

## 5.1 Facts

| Fact | Grain | Purpose |
|---|---|---|
| `fact_transaction` | Atomic transaction message-leg | Drill-down and non-standard slices |
| `fact_txn_lifecycle` | One business transaction / accumulating snapshot | Lifecycle, final state, net money |
| `fact_settlement_daily` | Settlement batch/institution/currency | Reconciliation, lag, exposure |

The three facts intentionally retain different grains. They must not be collapsed into one universal table.

## 5.2 Dimensions

The BI model contains 17 conformed dimensions, including:

- `dim_bin`
- `dim_channel`
- `dim_geography`
- `dim_response`
- `dim_transaction_type`
- `dim_status`
- date/time, institution, card, merchant, terminal, currency, server and related dimensions

## 5.3 Marts

The six principal marts are:

1. `mart_txn_hourly_ops`
2. `mart_txn_daily_exec`
3. `mart_institution_daily`
4. `mart_merchant_daily`
5. `mart_bin_risk_daily`
6. `mart_settlement_recon_daily`

## 5.4 KPI layer

The KPI layer provides:

- metric definitions
- baseline values
- z-score / anomaly context
- direction-aware thresholds
- warning/critical states
- cooldowns
- maintenance windows
- feedback

The Agent consumes these measurements and applies policy; it does not own the underlying analytical metric semantics.

## 5.5 Data quality

The model includes 12 logged DQ gates and six ETL procedures. DQ is upstream of application interpretation.

---

# 6. Package 3 — SERVE

## 6.1 Runtime topology

```text
                    ┌───────────────────────┐
                    │       FastAPI         │
                    │       /query         │
                    └──────────┬────────────┘
                               │
                               ▼
                    ┌───────────────────────┐
                    │      Core Pipeline    │
                    │                       │
                    │ PolicyGate            │
                    │ IntentExtractor       │
                    │ SQLGenerator          │
                    │ SQLReviewer           │
                    │ SQLGlotValidator      │
                    │ DuckDBExecutor        │
                    │ BaselineEnricher      │
                    │ DualSynthesizer       │
                    │ Memory Store          │
                    └──────────┬────────────┘
                               │
                  ┌────────────┴────────────┐
                  ▼                         ▼
            CEO + Analyst             persisted QueryRecord
               response                       │
                                              ▼
                                       secondary hooks
                                         / Sidecar
```

---

# 7. Primary User Request Contract

The canonical request pipeline is:

```text
UserQuery
  → PolicyGate
  → IntentExtractor
  → clarification/rejection check
  → SQLGenerator
  → SQLReviewer
  → optional single regeneration
  → SQLGlotValidator
  → DuckDBExecutor
  → BaselineEnricher
  → BaselineAwareDualSynthesizer
  → SQLiteMemoryStore.save()
  → secondary hooks
  → DualResponse
```

## 7.1 Intent

The intent is structured JSON, not SQL.

Example:

```json
{
  "category": "approval_rate",
  "confidence": 0.94,
  "entities": {
    "dimensions": ["server_name"],
    "time_range": "today",
    "filters": {
      "server_name": ["Tehran-01"]
    }
  },
  "needs_clarification": false
}
```

## 7.2 SQL generation

The SQL generator uses the semantic layer to determine:

- metric expression
- source
- allowed dimensions
- filter-to-column mapping
- declared joins
- mart-vs-fact routing

No raw user text is directly rendered as executable SQL.

## 7.3 SQL review

`SQLReviewer` may identify issues and request at most one regeneration cycle.

The reviewer is not the SQL execution authority.

## 7.4 SQL validation

`SQLGlotValidator` enforces the canonical SQL safety contract.

The validation result includes accessed tables and destructive-statement state.

## 7.5 Execution

`DuckDBExecutor` executes read-only statements and returns the normalized execution contract, including row count, columns, execution time and error state.

---

# 8. Semantic Layer

`src/config/semantic_layer.yaml` is the central semantic contract for Text2SQL.

It defines, among other properties:

```yaml
metrics:
  approval_rate:
    expression: "..."
    sources: [...]
    summary_column: approval_rate
    default_source: auto
    synonyms: [...]
```

The current architecture additionally enforces metric-specific allowed dimensions and compatible filters.

Unsupported dimensions or incompatible filters are rejected rather than silently discarded.

This is an important correctness rule:

> **The system must fail loudly when a requested analytical slice is incompatible with the metric contract.**

---

# 9. Baseline Enrichment

Baseline enrichment is metric-aware.

Supported families documented by Stage 3 include:

- total transactions
- approval rate
- total amount
- average switch latency
- stuck transactions
- hot-card count
- error count

Historical context includes windows such as:

- previous day
- same day last week
- 7-day average
- 30-day average
- 30-day extremes

The baseline layer must not fabricate a scalar comparison for arbitrary grouped results where such a comparison would be misleading.

---

# 10. Memory Semantics

Memory is non-authoritative.

Historical server/device/time context is carried forward only when the current conversational request contains a clear reference signal such as:

```text
همون
مثل قبل
same
previous
again
```

Explicit entities in the current request override historical candidates.

Ambiguous memory candidates must not silently alter query semantics.

Presentation preferences may be carried forward when they do not change query meaning.

This is a critical architectural guardrail because memory must never become an invisible query rewriter.

---

# 11. Policy and Security

`PolicyGate` is the application-level authorization boundary.

It checks:

- warehouse query role
- row limits
- protected-table policy
- memory access policy

The default request role is `analyst`; privileged behavior is not assumed by default.

Authentication itself is external to this project; the upstream gateway/IdP establishes trusted identity context.

Destructive SQL is rejected.

---

# 12. Dual Output Contract

The application produces two perspectives over the same analytical result:

```text
Business Analyst
    ↓
technical / analytical explanation

CEO
    ↓
strategic / concise interpretation
```

These are two presentation contracts over one validated execution, not two separate analytical engines.

This is important because the system's core value remains:

> **One correct analytical result, two fit-for-purpose explanations.**

---

# 13. Application Memory Store

The actual Stage 4 application memory schema is `query_records`.

```sql
CREATE TABLE IF NOT EXISTS query_records (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    intent_category TEXT,
    intent_entities TEXT,
    generated_sql TEXT,
    sql_metric TEXT,
    sql_dimensions TEXT,
    sql_filters TEXT,
    sql_joins TEXT,
    execution_row_count INTEGER DEFAULT 0,
    execution_success INTEGER DEFAULT 1,
    response_type TEXT,
    confidence REAL
);
```

This record is the authoritative application-level memory record for the query lifecycle.

---

# 14. Agent Layer

## 14.1 Responsibility

The Agent monitors KPI measurements and decides whether to:

- alert
- suppress
- log-only

It does not recompute the entire analytical model from raw transactions.

## 14.2 Runtime flow

```text
warehouse KPI measurement
      ↓
Agent observation
      ↓
maintenance check
      ↓
objective definition
      ↓
alert / suppression / log
      ↓
alert_log
```

## 14.3 Alert database — exact current schema

The current Stage 4 code creates `alert_log`:

```sql
CREATE TABLE IF NOT EXISTS alert_log (
    alert_id TEXT PRIMARY KEY,
    triggered_at TEXT NOT NULL,
    metric_name TEXT,
    server_sk INTEGER,
    severity TEXT,
    message TEXT,
    decision_reasoning TEXT,
    action_taken TEXT,
    sent_successfully INTEGER,
    acknowledged_at TEXT,
    resolved_at TEXT,
    was_real_incident INTEGER,
    false_positive INTEGER
);
```

This schema supersedes older draft names such as `alert_incidents_local`.

## 14.4 Design boundary

The Agent owns alert decisioning and alert persistence.

SML consumes the resulting signals; it does not replace the Agent.

---

# 15. Sidecar Layer

## 15.1 Responsibility

The Sidecar provides secondary analytical capabilities:

- follow-up suggestions
- anomaly investigation
- gap analysis

## 15.2 Safety architecture

Sidecar drill-down SQL goes through the same canonical SQL safety model as the core application.

The Sidecar uses a deterministic SQL generator and `sql_guard` before warehouse execution.

## 15.3 Sidecar modes

| Mode | Purpose | Current implementation |
|---|---|---|
| `suggest` | Follow-up suggestions | Subprocess call from API |
| `investigate` | Anomaly investigation | Fire-and-forget subprocess supported |
| `report` | Nightly gap analysis | Cron/standalone mode |

## 15.4 Investigator

The investigator follows KPI playbook steps from configuration and uses the deterministic SQL generator for drill-downs.

The LLM synthesizes a hypothesis from the resulting findings; it does not improvise executable SQL.

---

# 16. Sidecar State Database — exact current schema

The current Stage 4 `StateManager` creates the following tables.

## 16.1 Investigations

```sql
CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    query_id TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    hypothesis TEXT,
    confidence TEXT,
    drilldown_count INTEGER DEFAULT 0,
    report_path TEXT,
    status TEXT DEFAULT 'open',
    resolved_at TEXT
);
```

## 16.2 Follow-up suggestions

```sql
CREATE TABLE IF NOT EXISTS followup_suggestions (
    id TEXT PRIMARY KEY,
    query_id TEXT NOT NULL,
    session_id TEXT,
    suggestions_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    user_clicked INTEGER DEFAULT 0
);
```

## 16.3 Gap reports

```sql
CREATE TABLE IF NOT EXISTS gap_reports (
    id TEXT PRIMARY KEY,
    report_date TEXT NOT NULL,
    report_path TEXT NOT NULL,
    missing_metrics_json TEXT,
    missing_dimensions_json TEXT,
    generated_at TEXT NOT NULL
);
```

## 16.4 Agent run log

```sql
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    success INTEGER DEFAULT 0,
    output_summary TEXT,
    trace_id TEXT
);
```

## 16.5 Alert correlations

```sql
CREATE TABLE IF NOT EXISTS alert_correlations (
    id TEXT PRIMARY KEY,
    investigation_id TEXT,
    alert_id TEXT,
    metric_name TEXT,
    correlation_type TEXT,
    confidence REAL,
    created_at TEXT NOT NULL
);
```

This means the current Sidecar already has a local investigation-to-alert correlation mechanism.

---

# 17. Current Cross-System Relationships

The architecture does **not** have a completely correlation-free environment.

Existing relationships include:

```text
Sidecar investigation
      └── query_id → application query record

Sidecar alert correlation
      └── investigation_id + alert_id
```

However, there is still no first-class cross-system entity representing:

```text
many queries
+ many alerts
+ many investigations
+ lifecycle
+ resolution
```

as one Situation.

That is the verified architectural opportunity addressed by RFC-003.

---

# 18. Critical Main-Path Finding

The current implementation isolates optional Sidecar work from the primary response path. After a successful query is persisted, `EnrichedOrchestrator` invokes:

```python
trigger_suggest_async(record.id)
```

The legacy synchronous helper `trigger_suggest()` remains available for explicit callers outside the primary request path. The anomaly investigation path is also fire-and-forget:

```python
trigger_investigate(record.id, async_run=True)
```

Therefore the current primary path does not await either optional Sidecar operation.

## 18.1 Target invariant

The primary user response MUST NOT depend on RFC-003 Situation Memory, RFC-001 Council, or future learning systems.

# 19. Configuration Ownership

## 19.1 `semantic_layer.yaml`

Owns analytical semantics:

- metrics
- expressions
- sources
- dimensions
- joins
- glossary/synonyms

## 19.2 `kpi_definitions.yaml`

Owns KPI interpretation and operational behavior such as:

- thresholds
- direction
- cooldown
- business meaning
- investigation playbooks

## 19.3 `security_policies.yaml`

Owns application policy:

- role-based row limits
- query category access
- escalation rules

These are authoritative contracts for their respective concerns. Runtime projections may exist elsewhere, but they must not create competing semantic authorities.

---

# 20. Testing Contract

## 20.1 Existing test classes

The codebase contains:

- smoke tests
- Stage 4 tests
- contract regression tests from prior hardening stages
- deterministic generation paths

## 20.2 Golden test status

The architecture includes a deterministic golden-test runner and the current repository contains an 8-question canonical regression corpus; production-sized corpus expansion remains deployment hardening.

Therefore this RFC does not claim a completed 8-question production fixture set.

## 20.3 Required production-hardening tests

Before deployment as an external production service, verify:

- deterministic semantic generation
- SQL validation and protected-table behavior
- role authorization
- memory guardrails
- baseline correctness
- Sidecar SQL guard
- golden business questions
- load and latency
- external authentication integration

---

# 21. Security Model

```text
                ┌───────────────────────┐
                │ External Gateway / IdP│
                └──────────┬────────────┘
                           │ trusted identity
                           ▼
                    ┌──────────────┐
                    │  PolicyGate  │
                    └──────┬───────┘
                           ▼
                     Core SQL flow
                           │
                    SQLGlotValidator
                           │
                           ▼
                     Read-only DB
```

Sidecar follows the same principle:

```text
Sidecar SQL
   ↓
sql_guard
   ↓
SELECT-only / allow-listed / constrained
   ↓
warehouse
```

SML introduced by RFC-003 must be read-only against the existing production-side stores.

---

# 22. Failure Isolation

A secondary component must not take down the primary query service.

The following are non-critical to the user answer:

- Sidecar investigation
- Sidecar report generation
- future Situation correlation
- pattern analysis
- Evidence Builder
- Knowledge Council

Their failures should be observable and retryable rather than propagated into a successful query request.

---

# 23. Architectural Extension Point — RFC-003

RFC-003 adds a separate asynchronous layer:

```text
memory.db / query_records
        │
agent alert_log
        │
sidecar agent_state.db
        │
        ▼
Situation Correlator
        ▼
Situation Store
        ▼
Pattern Analyst
        ▼
RFC-001 Evidence Builder
```

SML must treat the existing systems as authoritative sources for their own facts.

SML owns only:

- Situation entity
- cross-system signal relationships
- situation history
- derived pattern-family metadata
- pattern evidence

---

# 24. Architectural Extension Point — RFC-001

RFC-001 consumes evidence derived from the runtime and SML.

Conceptual chain:

```text
Observed system behavior
        ↓
Situation / pattern evidence
        ↓
Evidence Package
        ↓
Hypothesis generation
        ↓
Council debate
        ↓
Knowledge Change Proposal
```

The Council must never be placed between the user and today's primary answer.

---

# 25. Verified Gaps of the Current Stage 4 Codebase

The following are real architectural gaps, not duplicate capabilities:

### G-001 — No unified Situation entity

Queries, alerts and investigations are stored separately.

### G-002 — No cross-system historical Situation memory

The current system can record local relationships, but does not maintain a first-class unified Situation history.

### G-003 — No recurring Situation family model

There is no dedicated historical clustering/drift layer over unified Situations.

### G-004 — No formal asynchronous event/outbox boundary

The request-path isolation is implemented with fire-and-forget process dispatch. A durable event/outbox mechanism remains future deployment hardening.

### G-005 — Golden fixture completeness requires verification

The deterministic runner exists, but the current archive does not prove a complete golden corpus.

---

# 26. What Must NOT Be Added to the Core

Do not add any of the following to `src/` merely to support future learning:

- Situation correlation logic
- pattern clustering
- historical family analysis
- Council reasoning
- playbook learning
- evidence debate
- autonomous knowledge mutation

The core remains a fast, deterministic query-serving system.

---

# 27. Target System Boundary

```text
                  PRIMARY QUERY SYSTEM

User
 ↓
src/
 ↓
Intent
 ↓
Deterministic SQL
 ↓
Validation
 ↓
Execution
 ↓
Baseline
 ↓
CEO + Analyst
 ↓
Memory
 ↓
RETURN

================ ASYNCHRONOUS BOUNDARY ================

Memory / Alerts / Investigations
 ↓
SML
 ↓
Evidence
 ↓
Council
 ↓
Governance
```

This is the target architectural separation for the next evolution.

---

# 28. Anti-Patterns

## A-001 — LLM SQL authoring

Rejected. Intent is the LLM boundary.

## A-002 — Raw-user-text SQL rendering

Rejected by design; SQL is produced from semantic contracts.

## A-003 — Silent semantic degradation

Unsupported dimensions/filters must fail rather than disappear.

## A-004 — Memory rewriting query intent

Historical context is a hint and cannot silently override explicit user intent.

## A-005 — Duplicate analytical ownership

Do not move metric semantics from the semantic layer into Agents or Sidecar.

## A-006 — Duplicate playbook authority

SML must not become a second production playbook owner.

## A-007 — Synchronous learning in the request path

Learning/correlation/council work must never become a user-response dependency.

---

# 29. Operational Readiness Position

This RFC describes an architecture that is substantially hardened for production-style use, including semantic contracts, policy enforcement, SQL safety, baseline enrichment, memory guardrails and Sidecar SQL safety.

However, the following remain deployment-specific hardening items rather than claims of universal completion:

- external IdP integration
- full golden fixture verification
- real environment integration
- load/latency validation at deployment scale
- production observability
- production event/outbox boundary (the current request path already uses fire-and-forget suggestion/investigation dispatch)

The architecture must not claim stronger operational guarantees than the repository verifies.

---

# 30. Definition of Done — RFC-004 Final

This RFC is considered architecturally complete when:

- [ ] Core `src/` responsibilities are documented from the current implementation.
- [ ] Agent ownership and actual `alert_log` contract are documented.
- [ ] Sidecar ownership and actual `agent_state.db` schema are documented.
- [ ] Existing local correlations are acknowledged.
- [ ] The absence of a first-class Situation entity is explicitly identified as the next-layer gap.
- [ ] The distinction between current implementation and target async architecture is explicit.
- [ ] Semantic authority is preserved.
- [ ] SQL safety authority is preserved.
- [ ] Dual CEO/Analyst response remains a core product contract.
- [ ] No future learning component is placed on the primary request path.

---

# 31. Final Architectural Position

The current project is best understood as four increasingly powerful concerns:

```text
PACKAGE 1
UNDERSTAND
    ↓
What does the transaction domain mean?

PACKAGE 2
MODEL
    ↓
How is that meaning represented analytically?

PACKAGE 3
SERVE
    ↓
How does a user obtain a safe, correct analytical answer?

RFC-003
SITUATION MEMORY
    ↓
What operational events are related over time?

RFC-001 + COUNCIL
KNOWLEDGE EVOLUTION
    ↓
What should the organization learn or change?
```

The primary user experience remains the same:

```text
User question
   ↓
fast deterministic analytical path
   ↓
CEO answer + Analyst answer
```

Everything after durable persistence is secondary intelligence:

```text
observe
   ↓
correlate
   ↓
remember
   ↓
learn
   ↓
propose
   ↓
govern
```

The central architectural rule is therefore:

> **Serve first. Learn second. Govern before changing.**

That rule preserves the value of the existing Stage 4 system while giving RFC-003 and RFC-001 a clean place to extend it without turning the core into an increasingly slow and fragile orchestration graph.

---

## Appendix A — Source Verification Notes

The final version was reconciled against the Stage 4 source archive, including the actual implementations of:

- `src/core/enriched_orchestrator.py`
- `src/core/sidecar_bridge.py`
- `src/adapters/sqlite_memory_adapter.py`
- `sidecar/core/state_manager.py`
- `sidecar/core/db_reader.py`
- `sidecar/agents/anomaly_investigator.py`
- `agent/agent_loop.py`
- `src/core/sql_generator.py`
- `src/core/sql_reviewer.py`
- `src/adapters/sqlglot_validator.py`
- configuration and test artifacts

Where the implementation differed from older RFC language, the implementation is treated as authoritative for the current-state description.

---

## Appendix B — Relationship to RFC-003 and RFC-001

```text
                  ┌───────────────────────┐
                  │     RFC-004 CORE      │
                  │   Understand/Model/   │
                  │        Serve          │
                  └───────────┬───────────┘
                              │ events / state
                              ▼
                  ┌───────────────────────┐
                  │      RFC-003 SML      │
                  │ Situation / Pattern   │
                  │ Operational Memory    │
                  └───────────┬───────────┘
                              │ evidence
                              ▼
                  ┌───────────────────────┐
                  │      RFC-001          │
                  │ Evidence Package      │
                  │ Hypothesis / Council  │
                  └───────────┬───────────┘
                              │ proposal
                              ▼
                  ┌───────────────────────┐
                  │      GOVERNANCE       │
                  │ Human approval / PR   │
                  │ CI/CD / controlled    │
                  │ evolution             │
                  └───────────────────────┘
```

**No downstream layer is allowed to become a prerequisite for the upstream user answer.**
