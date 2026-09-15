# RFC-003 — Situation Memory Layer (SML)

**Version:** 1.1  
**Status:** Architecture Baseline — Revised  
**Layer:** Asynchronous Operational Intelligence Layer  
**Date:** 2026-08-22  
**Scope:** Unified operational situation correlation and memory over the existing `src/`, `agents/`, and `sidecar/` capabilities

---

## 1. Abstract

The existing Text-to-SQL platform already contains three high-value operational signal domains:

1. **User query execution records** produced by `src/` and persisted in `memory.db`.
2. **KPI / alert incidents** produced by `agents/` and persisted in `agent_alerts.db`.
3. **Sidecar investigation state** produced by `sidecar/` and persisted in `agent_state.db`.

The existing system also contains local forms of correlation and investigation. The missing capability is not "correlation from zero"; it is a **first-class, cross-system Situation entity** that can represent multiple related queries, alerts, investigations, and outcomes as one traceable operational event.

SML adds only the missing layer:

```text
Existing Signals
      ↓
Deterministic Situation Correlator
      ↓
Situation Memory
      ↓
Situation Pattern Analyst
      ↓
Evidence Builder
      ↓
Knowledge Council
```

SML does **not** rebuild:

- Text-to-SQL
- semantic interpretation
- SQL generation
- SQL validation
- baseline enrichment
- KPI alerting
- anomaly investigation
- follow-up suggestion
- playbook ownership
- user response generation
- production mutation

The central invariant is:

> **SML MUST NEVER become a dependency of the user's primary request/response path.**

The user-facing path remains:

```text
User Question
  → Intent
  → Semantic Validation
  → SQL Generation
  → SQL Review
  → Execution
  → Baseline Enrichment
  → CEO + Analyst Response
  → Return
```

SML runs after durable persistence and consumes signals asynchronously.

---

# 2. Problem Statement

## 2.1 What already exists

The codebase already has substantial operational intelligence.

### `src/` / `memory.db`

Query history contains structured information including:

- query identity
- timestamp
- session/user context
- question
- category / intent
- confidence
- entities
- generated SQL
- selected source
- row count
- execution time
- execution status
- error information

The `src/` layer also performs:

- intent/entity extraction
- semantic metric and dimension validation
- baseline enrichment
- dual synthesis for analyst and CEO audiences
- role/policy enforcement
- SQL review and regeneration

### `agents/` / `agent_alerts.db`

The alerting layer provides:

- KPI definitions
- threshold decisions
- severity
- cooldown behavior
- maintenance-window suppression
- incident lifecycle
- human feedback on whether an alert was a real incident

### `sidecar/` / `agent_state.db`

The Sidecar provides:

- anomaly investigation
- safe drill-down SQL
- follow-up suggestion
- gap analysis
- investigation persistence
- local correlation with alerts and query context

The current implementation therefore contains **local intelligence and local relationships**.

---

## 2.2 What is missing

The missing abstraction is:

```text
SITUATION
```

A Situation is a traceable representation that answers:

> Which independently produced signals describe the same operational reality?

For example:

```text
Query Q-001
    +
Alert INC-042
    +
Investigation INV-007
    +
Resolution outcome
```

may represent one operational situation.

The current system stores these facts in separate domains. Relationships may exist through IDs such as `query_id` or local correlation records, but there is no single cross-system entity that owns the lifecycle of the combined event.

---

# 3. Architectural Principle

The following concepts must remain separate:

```text
Signal
  ≠
Situation
  ≠
Hypothesis
  ≠
Decision
  ≠
Change
```

### Signal

A fact emitted by an existing subsystem.

### Situation

A traceable representation of multiple signals that appear to describe the same operational reality.

### Hypothesis

An explanation proposed from evidence.

### Decision

A governance outcome about what to do.

### Change

An approved modification to knowledge, configuration, code, or policy.

This separation is fundamental to auditability and prevents SML from becoming a hidden decision engine.

---

# 4. Architectural Position

```text
                              USER
                               │
                               ▼
                    ┌─────────────────────┐
                    │        src/         │
                    │   Text-to-SQL Core  │
                    └──────────┬──────────┘
                               │
                ┌──────────────┴──────────────┐
                │                             │
                ▼                             ▼
        CEO + Analyst Response           Durable Query Record
                │                             │
                ▼                             ▼
              USER                     Async Event Boundary
                                              │
                                              ▼
                         ┌─────────────────────────────────┐
                         │     SITUATION MEMORY LAYER      │
                         │                                 │
                         │  Signal Adapters                │
                         │      ↓                          │
                         │  Deterministic Correlator       │
                         │      ↓                          │
                         │  Situation Store                │
                         │      ↓                          │
                         │  Pattern Analyst                │
                         └──────────────┬──────────────────┘
                                        │
                                        ▼
                               Evidence Builder
                                        │
                                        ▼
                              RFC-001 Evidence Package
                                        │
                                        ▼
                              Hypothesis Generator
                                        │
                                        ▼
                               Knowledge Council
                                        │
                                        ▼
                           Knowledge Change Proposal
                                        │
                                        ▼
                              Human Governance
```

---

# 5. Main Request Path Invariant

This is a mandatory architectural rule.

SML:

- MUST NOT be awaited by `src/`.
- MUST NOT execute before the user receives the primary response.
- MUST NOT generate SQL for the user's current request.
- MUST NOT perform warehouse queries as part of situation correlation.
- MUST NOT block `DualResponse`.
- MUST NOT cause a successful user query to fail if SML is unavailable.
- MUST NOT increase the latency budget of the synchronous query path.

Therefore:

```text
SML failure
   ↓
log / retry / dead-letter
   ↓
User request continues unaffected
```

---

# 6. The Existing Capability Boundary

| Capability | Existing Owner | SML Responsibility |
|---|---|---|
| Intent extraction | `src/` | Read resulting signal only |
| Semantic validation | `src/` | Read resulting signal only |
| SQL generation | `src/` | None |
| SQL review | `src/` | None |
| SQL execution | `src/` | None |
| Baseline enrichment | `src/` | Consume emitted result as evidence |
| CEO/Analyst synthesis | `src/` | None |
| KPI monitoring | `agents/` | Consume alert output |
| Alert lifecycle | `agents/` | Consume lifecycle state |
| Anomaly investigation | `sidecar/` | Consume investigation result |
| Safe drill-down SQL | `sidecar/` | None |
| Follow-up suggestion | `sidecar/` | None |
| Playbook execution/ownership | `sidecar/` | None |
| Cross-system Situation | Missing | **SML owns this** |
| Situation history | Missing | **SML owns this** |
| Pattern-family analysis | Missing | **SML owns this** |
| Evidence packaging | RFC-001 | SML supplies sources |
| Hypothesis generation | Council pipeline | SML supplies evidence |
| Governance approval | Governance layer | None |

---

# 7. Components

SML consists of five conceptual components.

## 7.1 Signal Adapters

Adapters normalize existing source systems into a common internal signal contract:

```text
QuerySignalAdapter
AlertSignalAdapter
InvestigationSignalAdapter
```

The adapters hide:

- SQLite schema details
- file paths
- storage implementation
- future event-bus changes

The Correlator MUST NOT depend directly on SQLite APIs.

---

## 7.2 Situation Correlator

The correlator is:

- deterministic
- zero-LLM
- auditable
- replayable

It answers only:

> Are these signals sufficiently related to belong to the same Situation?

It does NOT answer:

> What is the root cause?

---

## 7.3 Situation Store

The Situation Store is the system of record for cross-system operational situations.

It does not replace:

- `memory.db`
- `agent_alerts.db`
- `agent_state.db`

It stores the unified view.

---

## 7.4 Situation Pattern Analyst

This component analyzes historical situations.

It may:

- cluster similar situations
- identify recurring families
- calculate historical success rates
- detect pattern drift
- emit pattern signals

It MUST NOT:

- mutate production databases
- execute remediation
- become the owner of production playbooks
- silently change semantic knowledge
- make a final business decision

It is a source of **evidence**, not authority.

---

## 7.5 Evidence Adapter

The SML output is consumed by RFC-001 Evidence Builder.

Possible evidence source types:

```text
situation
pattern_family
pattern_drift
recurrence
resolution_outcome
correlation
```

The Evidence Builder decides how these become an Evidence Package.

---

# 8. Signal Contract

All adapters normalize source events to:

```yaml
signal:
  signal_id: "..."
  signal_type: "query|alert|investigation"
  observed_at: "2026-08-22T09:14:00+03:30"
  source_system: "src|agents|sidecar"
  source_reference: "..."
  entities:
    server: []
    bank: []
    metric: []
    kpi_name: []
    scope_key: []
    query_id: []
    incident_id: []
    investigation_id: []
  attributes: {}
  provenance:
    source_path: "..."
    source_hash: "..."
```

The contract is logical, not tied to a physical database schema.

---

# 9. Situation Correlation

## 9.1 Correlation inputs

The correlator uses:

- temporal proximity
- entity overlap
- semantic identifiers already emitted by source systems
- explicit IDs when available
- source provenance

The correlator SHOULD prefer structured IDs over text extraction whenever a source provides them.

---

## 9.2 Temporal window

Default:

```text
±15 minutes
```

The window MUST be configurable.

Critical alerts MAY use a larger window, but the configured value must be recorded in the Situation audit metadata.

---

## 9.3 Entity priority

Suggested initial weights:

| Entity | Weight |
|---|---:|
| server | 1.0 |
| bank / institution | 1.0 |
| query_id / incident_id linkage | 1.0 |
| metric | 0.8 |
| KPI name | 0.8 |
| scope key | 0.9 |
| time-of-day | 0.3 |
| user role | 0.1 |

The exact scoring function is configurable and versioned.

---

## 9.4 Correlation score

The score represents:

> likelihood that two signals describe the same operational Situation

It MUST NOT be interpreted as:

> probability that the observed root cause is correct

A correlation decision must record:

- rule version
- threshold
- candidate signals
- matched entities
- calculated score

---

## 9.5 Correlation result states

```text
MATCH
WEAK_MATCH
NO_MATCH
```

A `WEAK_MATCH` may be retained for later enrichment but must not automatically imply a definitive Situation merge.

---

# 10. Situation Entity

## 10.1 Core design

A Situation may contain many signals.

Therefore the model MUST NOT assume:

```text
1 query
1 alert
1 investigation
```

Instead:

```text
1 Situation
   ├── many query signals
   ├── many alert signals
   ├── many investigation signals
   └── many lifecycle events
```

---

## 10.2 Schema

```sql
CREATE TABLE situations (
    situation_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    closed_at TEXT,

    status TEXT NOT NULL
      CHECK(status IN (
        'open',
        'correlated',
        'resolved',
        'false_positive',
        'escalated',
        'stale'
      )),

    entities_json TEXT NOT NULL,
    narrative TEXT,

    first_signal_at TEXT NOT NULL,
    last_signal_at TEXT NOT NULL,
    signal_count INTEGER NOT NULL DEFAULT 0,

    correlation_confidence REAL,

    pattern_family_id TEXT,
    pattern_drift_score REAL,

    resolution_action TEXT,
    resolution_outcome TEXT
      CHECK(resolution_outcome IN (
        'resolved',
        'worsened',
        'no_change',
        'escalated'
      )),

    resolution_time_minutes INTEGER,

    immutable_snapshot INTEGER NOT NULL DEFAULT 1,
    evidence_hash TEXT
);

CREATE TABLE situation_signals (
    situation_id TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    signal_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    correlation_score REAL,

    PRIMARY KEY (
        situation_id,
        signal_type,
        signal_id
    )
);

CREATE TABLE situation_edges (
    edge_id TEXT PRIMARY KEY,
    from_situation_id TEXT NOT NULL,
    to_situation_id TEXT NOT NULL,

    edge_type TEXT NOT NULL
      CHECK(edge_type IN (
        'same_pattern',
        'same_family',
        'temporal_proximity',
        'related'
      )),

    confidence REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_situation_status
    ON situations(status);

CREATE INDEX idx_situation_time
    ON situations(first_signal_at, last_signal_at);

CREATE INDEX idx_situation_family
    ON situations(pattern_family_id);

CREATE INDEX idx_signal_lookup
    ON situation_signals(signal_type, signal_id);
```

---

# 11. Provenance and Traceability

Every Situation MUST be traceable back to its source records.

Example:

```text
Situation
   ↓
situation_signals
   ↓
source signal ID
   ↓
source DB / source path
   ↓
original record
```

The Situation Store is not permitted to become the sole copy of source facts.

Source systems remain authoritative for their original records.

---

# 12. Situation Lifecycle

```text
OPEN
 │
 ├── CORRELATED
 │      │
 │      ├── RESOLVED
 │      │
 │      ├── FALSE_POSITIVE
 │      │
 │      └── ESCALATED
 │
 └── STALE
```

A Situation may receive additional signals while open.

Once resolved:

- core signal references become immutable
- original timestamps remain immutable
- source provenance remains immutable

New interpretation may create new derived metadata or a linked Situation, but must not rewrite history.

---

# 13. Pattern Families

A Pattern Family is a historical grouping of similar Situations.

Example:

```yaml
family_id: "fam-mellat-afternoon-latency"

signature:
  bank:
    - "Mellat"
  metric:
    - "avg_latency"
  server:
    - "Tehran*"

total_occurrences: 12
successful_resolutions: 11
success_rate: 0.9167

avg_resolution_time_minutes: 8.5

drift_score: 0.05

stage: "ACTIVE"

source_situations:
  - "SIT-001"
  - "SIT-002"
```

---

# 14. Pattern Lifecycle

Pattern families MUST NOT immediately become production behavior.

```text
CANDIDATE
   ↓
SHADOW
   ↓
VALIDATED
   ↓
ACTIVE
   ↓
DEPRECATED
   ↓
REVOKED
```

## CANDIDATE

At least 3 historical occurrences.

## SHADOW

At least 5 occurrences and acceptable statistical confidence.

Recommended baseline:

```text
Wilson lower bound >= 0.65
```

No operational action is allowed.

## VALIDATED

Human approval.

## ACTIVE

At least 7 days of validated historical success.

Only ACTIVE patterns may generate operational recommendations.

## DEPRECATED

Performance degradation.

## REVOKED

Pattern caused material harm or is explicitly invalidated.

A REVOKED pattern must never automatically become ACTIVE again.

---

# 15. Pattern Drift

Pattern drift measures how much the latest Situation differs from a known family.

Example:

```text
0.00 → nearly identical
0.20 → minor deviation
0.40 → significant deviation
0.70 → likely new pattern
1.00 → completely novel
```

Default review threshold:

```text
drift_score > 0.40
```

A high-drift Situation must produce a review signal rather than an automatic operational action.

---

# 16. Situation Pattern Analyst

## 16.1 Fast Loop

Recommended frequency:

```text
every 5 minutes
```

Responsibilities:

- inspect recent/open Situations
- match them to known ACTIVE families
- detect recurrence
- generate pattern signals
- flag drift

It MUST NOT execute remediation.

---

## 16.2 Deep Analysis

Recommended frequency:

```text
nightly
```

Responsibilities:

- cluster historical Situations
- calculate family statistics
- calculate drift
- create or update family metadata
- create evidence candidates

---

# 17. Output Contract

The Pattern Analyst produces structured pattern/evidence signals.

It does not directly change the production playbook.

Example:

```json
{
  "ts": "2026-08-22T09:18:00+03:30",
  "type": "pattern_signal",
  "situation_id": "SIT-001",
  "family_id": "fam-mellat-afternoon-latency",
  "confidence": 0.89,
  "occurrences": 12,
  "success_rate": 0.9167,
  "drift_score": 0.05,
  "recommended_review": false
}
```

This is an **evidence-producing output**, not a production command.

---

# 18. Playbook Boundary

SML MUST NOT become a second playbook owner.

The existing Sidecar playbook mechanism remains authoritative for Sidecar behavior.

SML may:

- observe playbook references
- correlate outcomes
- learn historical effectiveness
- surface pattern evidence

SML MUST NOT silently mutate the authoritative playbook.

Any future change to a production playbook MUST pass through its existing governance and validation path.

---

# 19. Relationship with RFC-001

SML is an evidence source for RFC-001.

The relationship is:

```text
Source Systems
      ↓
Situation Memory
      ↓
Pattern Signals
      ↓
Evidence Builder
      ↓
Evidence Package
      ↓
Hypothesis Generator
      ↓
Council
      ↓
Knowledge Change Proposal
```

SML does not decide what the knowledge change should be.

A Situation is itself eligible to be an evidence source even when no pattern family exists yet.

---

# 20. Domain Knowledge Boundary

The project has rich domain knowledge:

- transaction lifecycle
- semantic dimensions
- metric contracts
- KPI catalog
- DQ rules
- marts
- domain dictionary

This knowledge is **context**, not raw Situation signals.

Therefore:

```text
Situation Facts
      +
Domain Context
      ↓
Evidence Builder
```

The Correlator itself SHOULD NOT require the full domain model to perform basic correlation.

This keeps correlation fast and deterministic.

---

# 21. Main Path Performance

SML is an asynchronous consumer.

Performance requirements:

| Requirement | Target |
|---|---:|
| Impact on primary query latency | 0 ms blocking dependency |
| Correlation processing | < 2 sec for normal batch |
| Throughput | ≥ 1000 signals/minute |
| Pattern analysis batch | < 60 sec for 24h window |
| SML failure impact on user query | None |

These are SML requirements, not user-query latency guarantees.

---

# 22. Failure Isolation

If SML fails:

```text
User request
   ↓
continues normally

SML
   ↓
retry
   ↓
dead-letter / alert
```

No SML exception may propagate into:

- Text-to-SQL execution
- SQL review
- response synthesis
- HTTP response generation

---

# 23. Ingestion Strategy

## MVP

Polling is acceptable:

```text
every 60 seconds
```

The polling interval MUST be configurable.

## Target Architecture

Introduce an asynchronous event boundary / outbox.

```text
Source System
   ↓
Durable Event
   ↓
SML Consumer
```

Benefits:

- replay
- retry
- backpressure
- ordering
- reduced source DB polling
- decoupling
- easier observability

The event boundary must remain outside the user's response path.

---

# 24. Idempotency and Late Arrivals

Every signal must be processed idempotently.

The same signal arriving twice MUST NOT create duplicate `situation_signals` rows.

Recommended identity:

```text
(source_system, signal_type, signal_id)
```

Late signals must be attachable to an existing open Situation without rewriting original history.

---

# 25. False Correlation Handling

A correlation may later be determined incorrect.

The Situation lifecycle must support:

```text
CORRELATED
   ↓
FALSE_POSITIVE
```

The original correlation decision remains preserved.

The false-positive result becomes learning evidence for future correlation scoring.

---

# 26. Security Boundary

### Read-only

```text
memory.db
agent_alerts.db
agent_state.db
```

### Own write storage

```text
situation_memory.db
pattern_families.json
situation_predictions.jsonl
```

### Forbidden writes

```text
warehouse
memory.db
agent_alerts.db
agent_state.db
semantic_layer.yaml
kpi_definitions.yaml
playbook.yaml
production configuration
```

SML must not execute arbitrary production SQL.

---

# 27. Privacy and Sensitive Data

SML should store identifiers and operational metadata rather than duplicating raw sensitive payloads.

Where possible:

- use references instead of copying raw query text
- redact sensitive values
- avoid duplicating PAN-like or credential data
- preserve only the information needed for correlation and audit

The source system remains authoritative for sensitive details.

---

# 28. Validation Rules

### V-001 — Deterministic Correlation

Core correlation must use deterministic rules.

### V-002 — Read-Only Production

SML cannot write to production source databases.

### V-003 — Minimum Signal

A Situation must have at least one valid signal.

### V-004 — Multi-Signal Integrity

Every attached signal must be traceable to an existing source record.

### V-005 — Immutable Resolution History

Resolved Situation core facts cannot be silently rewritten.

### V-006 — Pattern Activation

ACTIVE requires:

- sufficient occurrences
- acceptable statistical bound
- human validation
- shadow success period

### V-007 — Drift Review

High drift triggers human review.

### V-008 — Idempotency

Duplicate signal ingestion must not create duplicate relations.

### V-009 — Main-Path Isolation

SML must never block or fail the primary query path.

### V-010 — Playbook Ownership

SML cannot directly modify the authoritative production playbook.

---

# 29. Anti-Patterns

## A-001 — LLM Correlation

Do not use LLMs for the core fact-level correlation.

## A-002 — Rebuilding Existing Capabilities

Do not duplicate SQL generation, alerting, anomaly investigation, or baseline logic.

## A-003 — Main Path Dependency

Never await SML from the user's request path.

## A-004 — Situation as Root Cause

A Situation is not proof of root cause.

## A-005 — Single-Signal Certainty

One signal may form an open Situation, but cannot imply a confirmed incident.

## A-006 — Second Playbook Authority

SML must not create an independent production playbook authority.

## A-007 — Mutable History

Do not rewrite historical source relationships after resolution.

## A-008 — Action Before Validation

No pre-emptive operational action from Candidate or Shadow families.

---

# 30. Sample End-to-End Walkthrough

## 09:14 — User Query

User asks:

> «چرا تراکنش‌های تهران کنده؟»

`src/` stores the query record.

The user receives the normal CEO + Analyst response.

SML is not involved yet.

## 09:15 — Alert

`agents/` records a latency KPI incident.

Again, no effect on the original user response.

## 09:17 — Sidecar Investigation

`sidecar/` creates an investigation record.

The existing Sidecar logic continues to run exactly as before.

## 09:18 — SML Correlation

The Correlator consumes the three signals.

It finds:

```text
query:
server = Tehran-01
metric = avg_latency

alert:
scope = Tehran-01
metric = avg_latency

investigation:
query_id = Q-001
```

The score exceeds the configured threshold.

A Situation is created:

```text
SIT-20260820-001

Signals:
Q-001
INC-042
INV-007

Status:
CORRELATED

Correlation:
0.91
```

## Later — Resolution

Ops resolves the incident.

SML records:

```text
resolution_outcome = resolved
resolution_time_minutes = 11
```

## Nightly Analysis

The Pattern Analyst finds:

```text
12 similar situations
11 successful resolutions
success rate ≈ 91.7%
drift = 0.05
```

The family remains or becomes ACTIVE only if all lifecycle requirements are satisfied.

## Evidence

The Pattern Analyst emits a pattern signal.

RFC-001 Evidence Builder consumes it.

It may combine the situation history with:

- KPI deterioration
- user corrections
- Sidecar findings
- DQ results
- domain knowledge gaps
- golden test failures

The Knowledge Council then evaluates hypotheses.

---

# 31. Relationship to the Knowledge Council

SML does not replace the Council.

SML improves the Council's evidence quality.

Without SML:

```text
many isolated observations
```

With SML:

```text
repeated operational situations
        ↓
historical families
        ↓
recurrence
        ↓
drift
        ↓
higher-quality evidence
```

The Council can then ask:

> Why does this recurring situation continue to occur?

rather than:

> Did something unusual happen today?

---

# 32. Implementation Plan

## Phase 1 — Situation Store

- [ ] Create `situation_memory.db`
- [ ] Implement `situations`
- [ ] Implement `situation_signals`
- [ ] Implement `situation_edges`
- [ ] Add indexes
- [ ] Add idempotency constraints

## Phase 2 — Signal Adapters

- [ ] `QuerySignalAdapter`
- [ ] `AlertSignalAdapter`
- [ ] `InvestigationSignalAdapter`
- [ ] normalize source records
- [ ] preserve provenance

## Phase 3 — Deterministic Correlator

- [ ] temporal matching
- [ ] entity extraction
- [ ] structured-ID matching
- [ ] weighted scoring
- [ ] open-situation attachment
- [ ] orphan handling
- [ ] late-arrival handling

## Phase 4 — Pattern Analyst

- [ ] historical clustering
- [ ] pattern family persistence
- [ ] recurrence calculation
- [ ] success-rate calculation
- [ ] drift detection
- [ ] Candidate / Shadow lifecycle

## Phase 5 — Evidence Integration

- [ ] situation evidence adapter
- [ ] pattern signal adapter
- [ ] RFC-001 contract integration
- [ ] audit/replay support

## Phase 6 — Async Boundary

- [ ] MVP polling
- [ ] durable event/outbox design
- [ ] retry policy
- [ ] dead-letter handling
- [ ] observability

---

# 33. Non-Functional Requirements

### Reliability

SML failure cannot affect user-query availability.

### Auditability

Every Situation must be reconstructible from source references.

### Reproducibility

Correlation decisions must be replayable using the same rule version.

### Determinism

The core Correlator must produce the same result from the same inputs and configuration.

### Scalability

The architecture should support at least 1000 incoming signals/minute for the initial deployment target.

### Observability

At minimum track:

- signal ingestion count
- correlation count
- false-positive count
- open situation count
- correlation latency
- pattern family count
- drift events
- rejected signals
- processing backlog

---

# 34. Decision Record

## Decision

Create an asynchronous Situation Memory Layer that:

1. consumes existing operational signals,
2. creates a first-class Situation entity,
3. stores cross-system historical relationships,
4. analyzes recurrence and drift,
5. exposes outputs as evidence for RFC-001.

## Rejected Alternative 1

Create another agent that independently investigates incidents.

**Rejected:** duplicates Sidecar.

## Rejected Alternative 2

Make SML the owner of production playbooks.

**Rejected:** creates a second authority.

## Rejected Alternative 3

Run SML synchronously during user queries.

**Rejected:** violates the primary latency and availability invariant.

## Rejected Alternative 4

Send raw logs directly to the Council.

**Rejected:** insufficient structure, traceability, and correlation semantics.

---

# 35. Trade-offs

## Benefits

- First-class operational Situation
- Historical recurrence
- Cross-system traceability
- Better Evidence Package quality
- Strong separation of facts and reasoning
- Minimal disruption to existing capabilities
- Asynchronous failure isolation
- Reusable operational memory

## Costs

- Additional storage
- Correlation logic maintenance
- Schema/version management
- Pattern analysis complexity
- Need for human validation of active families
- Event/replay infrastructure over time

---

# 36. Future Evolution

Potential future features:

- event bus instead of polling
- richer causal relationships
- statistical change-point detection
- cross-session operational narratives
- domain-aware correlation
- federated situation graphs
- advanced recurrence prediction

These are future capabilities, not v1 requirements.

---

# 37. Definition of Done

SML v1 is complete when:

- [ ] A Situation can contain multiple queries, alerts, and investigations.
- [ ] All signals remain traceable to their source systems.
- [ ] Correlation is deterministic and replayable.
- [ ] No SML code runs on the primary user response path.
- [ ] SML has zero write access to source production databases.
- [ ] Duplicate signal ingestion is idempotent.
- [ ] Resolved Situations preserve immutable historical facts.
- [ ] Pattern families support Candidate → Shadow → Validated → Active lifecycle.
- [ ] Pattern drift can trigger human review.
- [ ] SML does not own the authoritative production playbook.
- [ ] RFC-001 Evidence Builder can consume Situation-derived evidence.
- [ ] Human audit demonstrates acceptable correlation accuracy.
- [ ] Performance target of 1000 signals/minute is demonstrated.
- [ ] SML failure does not fail user queries.

---

# 38. Final Architectural Position

SML is not a replacement for the existing system.

It is not a second Text-to-SQL system.

It is not a second Sidecar.

It is not a second Alert Agent.

It is not a second Playbook Engine.

It is the missing **cross-system operational memory abstraction**.

The existing system already answers:

```text
What did the user ask?
What KPI fired?
What did the Sidecar investigate?
What was the response?
```

SML adds:

```text
Which of these belong to the same operational Situation?
Has this Situation happened before?
Does it belong to a recurring family?
Is the family drifting?
What evidence does that history contribute to the learning loop?
```

The final separation is:

```text
src/
    Answers the user.

agents/
    Detects KPI conditions.

sidecar/
    Investigates anomalies.

SML/
    Connects operational reality over time.

Evidence Builder/
    Packages traceable evidence.

Council/
    Reasons over evidence.

Governance/
    Approves changes.
```

And the most important invariant remains:

> **The user asks a question and gets the normal CEO + Analyst answer without waiting for SML, Council, or any learning process.**

SML may learn after the answer.

It may enrich tomorrow's evidence.

It may reveal a recurring pattern.

But it must never stand between the user and today's answer.
