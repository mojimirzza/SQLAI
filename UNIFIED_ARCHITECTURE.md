# Unified Architecture: Text-to-SQL + Alert Agent + Sidecar

## Overview

This is a unified analytics platform for switch card banking transaction monitoring. It consists of three independent but complementary systems:

1. **Main Text-to-SQL API** — Answers user questions with dual-perspective responses (BA + CEO)
2. **Alert Agent** — Proactive monitoring that detects statistical anomalies and alerts ops
3. **Sidecar** — Analytical intelligence that investigates anomalies, suggests follow-ups, and reports coverage gaps

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           INFORMIX 14.10 (Source)                           │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │
│  │ dim_date│  │ dim_time│  │dim_server│  │dim_term │  │dim_status│         │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘         │
│       └─────────────┴─────────────┴─────────────┴─────────────┘             │
│                              │                                              │
│                         ┌────┴────┐                                         │
│                         │ fact_txn│                                         │
│                         └────┬────┘                                         │
│                              │                                              │
│              ┌───────────────┴───────────────┐                              │
│              │ fact_txn_daily_summary          │                              │
│              │ (baseline + anomaly detection)  │                              │
│              └───────────────┬───────────────┘                              │
└──────────────────────────────┼──────────────────────────────────────────────┘
                               │
                               ▼ ETL Export
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DUCKDB warehouse.db                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  Tables: fact_transaction, dim_*, fact_txn_daily_summary            │   │
│  │  metric_daily_baseline (alert agent source)                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  MAIN API       │  │  ALERT AGENT    │  │  SIDECAR        │
│  (src/)         │  │  (agent/)       │  │  (sidecar/)     │
│                 │  │                 │  │                 │
│  User Query     │  │ Every 15 min    │  │ Mode: report    │
│    │            │  │    │            │  │  (daily cron)   │
│    ▼            │  │    ▼            │  │                 │
│  Intent Extract │  │  Read baseline  │  │ Mode: investigate│
│    │            │  │    │            │  │  (event-driven) │
│    ▼            │  │    ▼            │  │                 │
│  SQL Generator  │  │  Decide: alert/ │  │ Mode: suggest   │
│    │            │  │  suppress/log   │  │  (per-query)    │
│    ▼            │  │    │            │  │                 │
│  DuckDB Execute │  │    ▼            │  │                 │
│    │            │  │  Send Slack     │  │                 │
│    ▼            │  │    │            │  │                 │
│  Baseline Enrich│  │    ▼            │  │                 │
│    │            │  │  Write          │  │                 │
│    ▼            │  │  agent_alerts.db│  │                 │
│  Dual Synthesis │  │                 │  │                 │
│    │            │  │                 │  │                 │
│    ▼            │  │                 │  │                 │
│  Save memory.db │  │                 │  │                 │
│    │            │  │                 │  │                 │
│    └──► trigger_suggest_async() ───►│  │                 │
│    └──► trigger_investigate() ─────►│  │                 │
│                                     │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │                     │
         ▼                     ▼                     ▼
   data/memory.db       data/agent_alerts.db   data/agent_state.db
   (query history)      (alert decisions)      (sidecar state)
```

## Data Flow

### 1. User Query Flow
```
User → API → Intent Extract → SQL Gen → DuckDB → Baseline Enrich → Dual Synthesis
                                              │
                                              ├──► Save to memory.db
                                              ├──► trigger_suggest_async() → sidecar
                                              └──► if anomaly: trigger_investigate() → sidecar
```

### 2. Alert Agent Flow
```
Every 15 min → Read metric_daily_baseline → Find unalerted anomalies
                    │
                    ├──► In maintenance? → SUPPRESS
                    ├──► SLA breach? → ALERT (HIGH)
                    ├──► z_score > 3.0? → ALERT (MEDIUM)
                    ├──► z_score > 1.5? → ALERT (LOW)
                    └──► Otherwise → LOG_ONLY
                              │
                              ▼
                    Send Slack → #ops-critical or #daily-summary
                              │
                              ▼
                    Write to agent_alerts.db (alert_log table)
```

### 3. Sidecar Flow

**Mode: report (daily cron)**
```
Read memory.db (last 7 days) + semantic_layer.yaml + agent_alerts.db
    │
    ▼
LLM analyzes: missing metrics, missing dimensions, alert patterns
    │
    ▼
Write: reports/gap_report_YYYYMMDD_HHMMSS.md
```

**Mode: investigate (event-driven)**
```
Trigger: anomaly_flag=true in memory.db (or alert agent fires)
    │
    ▼
Read query record + alert history + warehouse data
    │
    ▼
LLM plans drill-down SQLs → Execute on DuckDB → Synthesize hypothesis
    │
    ▼
Write: reports/investigation_<query_id>_YYYYMMDD_HHMMSS.md
Save: agent_state.db (investigations + alert_correlations)
```

**Mode: suggest (per-query)**
```
Trigger: after every successful query
    │
    ▼
Read query record + session history + semantic layer
    │
    ▼
LLM generates 2-3 follow-up questions
    │
    ▼
Return: JSON { "suggestions": [...] }
Save: agent_state.db (followup_suggestions)
```

## Database Separation

| Database | Owner | Writes | Reads | Purpose |
|----------|-------|--------|-------|---------|
| `data/warehouse.db` | Main API | ❌ Read-only | ✅ | DuckDB warehouse from Informix ETL |
| `data/memory.db` | Main API | ✅ | ✅ | Query history, intent, results |
| `data/agent_alerts.db` | Alert Agent | ✅ | ✅ | Alert decisions, alert_log |
| `data/agent_state.db` | Sidecar | ✅ | ✅ | Sidecar investigations, suggestions, correlations |

**Critical rule:** No system writes to another system's database. Each owns its own state.

## Integration Points

### Main API → Sidecar (via sidecar_bridge.py)

```python
# In enriched_orchestrator.py, after successful query:

# 1. Follow-up suggestions (sync, ~1-2s, best-effort)
from core.sidecar_bridge import trigger_suggest
trigger_suggest_async(record.id)
response.suggested_followups = suggestions

# 2. Anomaly investigation (async, non-blocking)
if baseline.anomaly_flag:
    from core.sidecar_bridge import trigger_investigate
    trigger_investigate(record.id, async_run=True)
```

### Alert Agent → Sidecar (via shared agent_alerts.db)

The sidecar reads `agent_alerts.db` to:
- Correlate investigations with past alerts
- Identify metrics that trigger frequent false positives
- Enrich gap reports with alert patterns

### Cron Schedule

```bash
# Alert Agent — every 15 minutes
*/15 * * * * cd /path/to/project && python agent/main.py >> /var/log/alert_agent.log 2>&1

# Sidecar Gap Report — daily at midnight
0 0 * * * cd /path/to/project/sidecar && python main.py --mode report >> /var/log/sidecar_report.log 2>&1
```

## File Structure

```
project/
├── src/                          ← Main Text-to-SQL API
│   ├── core/
│   │   ├── enriched_orchestrator.py   (wires sidecar triggers)
│   │   ├── sidecar_bridge.py          (NEW — lightweight integration)
│   │   └── ...
│   ├── api/
│   ├── adapters/
│   └── config/
│
├── agent/                        ← Alert Agent (colleagues' module)
│   ├── main.py
│   ├── agent_loop.py
│   ├── objective_definer.py
│   ├── tools/
│   └── notifiers/
│
├── sidecar/                      ← Analytical Sidecar (NEW)
│   ├── main.py
│   ├── config.yaml
│   ├── core/
│   │   ├── agent.py              (ReAct micro-framework)
│   │   ├── db_reader.py          (reads all 4 databases)
│   │   ├── llm_client.py
│   │   ├── state_manager.py
│   │   └── tool_registry.py
│   ├── agents/
│   │   ├── gap_analyst.py
│   │   ├── anomaly_investigator.py
│   │   └── followup_suggester.py
│   ├── prompts/
│   └── reports/
│
├── data/
│   ├── warehouse.db              ← DuckDB (ETL from Informix)
│   ├── memory.db                 ← SQLite (query history)
│   ├── agent_alerts.db           ← SQLite (alert agent decisions)
│   └── agent_state.db            ← SQLite (sidecar state)
│
├── sql/
│   └── create_baseline_tables_duckdb.sql
│
├── prompts/                      ← Main API prompts
├── scripts/
│   └── init_db.py                ← Creates ALL tables including metric_daily_baseline
└── README.md
```

## Running the Systems

### 1. Initialize All Databases
```bash
python scripts/init_db.py
```
This creates:
- `data/warehouse.db` (DuckDB) with all star schema tables
- `data/memory.db` (SQLite) with query_records
- `data/agent_alerts.db` (SQLite) with alert_log
- `data/agent_state.db` (SQLite) with sidecar tables

### 2. Run the Main API
```bash
python run.py
# or
python src/api/main_enriched.py
```

### 3. Run the Alert Agent (separate terminal or cron)
```bash
# One-time run
python agent/main.py

# Or with cron (every 15 min)
*/15 * * * * cd /path/to/project && python agent/main.py
```

### 4. Run Sidecar Modes

```bash
cd sidecar

# Daily gap report
python main.py --mode report

# Investigate a specific anomaly
python main.py --mode investigate --query-id <uuid>

# Generate follow-up suggestions
python main.py --mode suggest --query-id <uuid>
```

## Key Design Decisions

1. **Database isolation:** Each system owns its own SQLite. No cross-system writes.
2. **Alert agent is rule-based (Phase 1):** Deterministic, fast, reliable. LLM enhancement is Phase 2.
3. **Sidecar is LLM-powered:** Uses GPT-4o-mini for analysis, synthesis, and suggestion generation.
4. **Main API triggers sidecar via bridge:** Subprocess calls with timeouts. Sidecar failures never break the main query.
5. **Sidecar reads alert agent DB:** For correlation and context enrichment, but never writes to it.
6. **All outputs are human-reviewed:** Gap reports → developer review. Investigation reports → analyst review. Suggestions → user optional clicks.

## Troubleshooting

**"metric_daily_baseline table not found"**
→ Run `python scripts/init_db.py` to create all tables.

**"Sidecar suggestions not appearing"**
→ Check `data/agent_state.db` for followup_suggestions table. Check sidecar logs.

**"Alert agent not sending Slack"**
→ Set `SLACK_WEBHOOK_URL` env var. Falls back to console if unset.

**"Warehouse.db locked"**
→ Ensure main API and alert agent both use read-only connections for queries. Only alert agent writes `alerted` flag.
