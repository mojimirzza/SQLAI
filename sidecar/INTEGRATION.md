# Sidecar Integration Guide (Unified System)

## What This Is

The sidecar is one of three independent systems in the unified analytics platform:

1. **Main API** (`src/`) — Text-to-SQL with dual-perspective responses
2. **Alert Agent** (`agent/`) — Proactive anomaly detection and Slack alerts
3. **Sidecar** (`sidecar/`) — Analytical intelligence (this module)

The sidecar reads data produced by the other two systems but never modifies them.

## Architecture

```
Main Project (src/)          Alert Agent (agent/)          Sidecar (sidecar/)
    │                              │                              │
    ├── data/memory.db  ◄─────────┤  read-only                   │  read-only
    ├── data/warehouse.db ◄───────┤  read-only                   │  read-only
    │                              ├── data/agent_alerts.db ◄────┤  read-only
    │                              │  (alert decisions)           │
    │                              │                              ├── data/agent_state.db
    │                              │                              │  (sidecar's own DB)
    │                              │                              ├── reports/*.md
    │                              │                              │
    │                              │                              └── main.py (3 modes)
```

## Three Modes

### Mode 1: Gap Report (`--mode report`)

**Trigger:** Daily cron (recommended: midnight)
**Input:** `memory.db` (7-day query history) + `semantic_layer.yaml` + `agent_alerts.db`
**Output:** `reports/gap_report_YYYYMMDD_HHMMSS.md`
**Value:** Tells developers what metrics users are asking for but the system cannot answer. Also identifies metrics that trigger frequent alerts (may need better baseline definitions).

**Run:**
```bash
cd sidecar
python main.py --mode report
```

**Cron:**
```bash
0 0 * * * cd /path/to/project/sidecar && python main.py --mode report >> /var/log/sidecar_report.log 2>&1
```

### Mode 2: Anomaly Investigation (`--mode investigate`)

**Trigger:** Event-driven (when main API detects anomaly OR alert agent fires)
**Input:** Query UUID from `memory.db` + `warehouse.db` + `agent_alerts.db` (alert history)
**Output:** `reports/investigation_<query_id>_YYYYMMDD_HHMMSS.md`
**Value:** Auto-generates drill-down SQLs, executes them, and synthesizes a root-cause hypothesis. Correlates with alert agent history for richer context.

**Run manually:**
```bash
cd sidecar
python main.py --mode investigate --query-id <uuid>
```

**Auto-trigger from main API:** Already wired in `src/core/enriched_orchestrator.py` via `sidecar_bridge.py`.

### Mode 3: Follow-up Suggestions (`--mode suggest`)

**Trigger:** Per-query (after every successful query)
**Input:** Query UUID from `memory.db` + session history + `semantic_layer.yaml`
**Output:** JSON array of 2-3 follow-up questions
**Value:** Helps analysts discover deeper insights without thinking of the next question themselves.

**Run manually:**
```bash
cd sidecar
python main.py --mode suggest --query-id <uuid>
```

**Auto-trigger from main API:** Already wired in `src/core/enriched_orchestrator.py` as a fire-and-forget async subprocess. Suggestions are persisted for later retrieval; they are not a synchronous dependency of the primary response.

## Installation

```bash
cd sidecar
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy your main project's `.env` (for OPENAI_API_KEY) or set it manually:
```bash
export OPENAI_API_KEY=sk-...
```

## Configuration

Edit `config.yaml`:

```yaml
paths:
  memory_db: "../data/memory.db"
  warehouse_db: "../data/warehouse.db"
  semantic_layer: "../src/config/semantic_layer.yaml"
  agent_alerts_db: "../data/agent_alerts.db"  # Alert agent's DB (read-only)
  agent_state_db: "../data/agent_state.db"      # Sidecar's own DB
  reports_dir: "./reports"

llm:
  model: "gpt-4o-mini"
  temperature: 0.0

thresholds:
  gap_analyst:
    lookback_days: 7
    min_confidence: 0.70
  anomaly_investigator:
    max_drilldown_queries: 5
  followup_suggester:
    max_suggestions: 3
```

## How It Integrates with the Alert Agent

The sidecar reads `agent_alerts.db` (the alert agent's own database) to enrich its analysis:

| Sidecar Agent | Alert Agent Data Used | Purpose |
|---------------|----------------------|---------|
| Gap Analyst | Alert history (7 days) | Identify metrics that trigger frequent alerts but have poor semantic coverage |
| Anomaly Investigator | Open alerts + recent alert history | Correlate current anomaly with past alerts on same metric/server |
| Follow-up Suggester | None | Purely query-history driven |

**Important:** The sidecar only **reads** `agent_alerts.db`. It never writes to it. The alert agent owns that database.

## Monitoring the Sidecar

Check agent runs:
```bash
sqlite3 data/agent_state.db "SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT 10;"
```

Check open investigations:
```bash
sqlite3 data/agent_state.db "SELECT * FROM investigations WHERE status = 'open';"
```

Check alert correlations:
```bash
sqlite3 data/agent_state.db "SELECT * FROM alert_correlations ORDER BY created_at DESC LIMIT 10;"
```

Check suggestion history:
```bash
sqlite3 data/agent_state.db "SELECT * FROM followup_suggestions ORDER BY created_at DESC LIMIT 10;"
```

## Customization

### Change the LLM model
Edit `config.yaml`:
```yaml
llm:
  model: "gpt-4o"  # or "gpt-3.5-turbo" for cheaper runs
```

### Adjust thresholds
Edit `config.yaml`:
```yaml
thresholds:
  gap_analyst:
    lookback_days: 14  # analyze 2 weeks
    min_confidence: 0.60  # catch more borderline queries
```

### Add a new tool
Edit `core/tool_registry.py`:
```python
@tool(name="my_tool", description="Does something useful")
def my_tool(param: str) -> str:
    return f"Result: {param}"
```

## Troubleshooting

**"OPENAI_API_KEY not configured"**
→ Set env var or create `.env` file in project root.

**"Query not found"**
→ The query_id must exist in `data/memory.db`. Check with:
```bash
sqlite3 data/memory.db "SELECT id, query_text FROM query_records ORDER BY timestamp DESC LIMIT 5;"
```

**"agent_alerts.db not found"**
→ Run `python scripts/unified_setup.py` to initialize all databases.

**"DuckDB database is locked"**
→ Ensure main API is not writing to warehouse.db when sidecar reads. The main API should only read from DuckDB.

**Reports are empty**
→ Check that `data/memory.db` has records. Run a few queries through the main API first.

## Philosophy

This sidecar follows three principles:

1. **Zero risk to other systems** — read-only, separate DB, no imports from `src/` or `agent/`
2. **Human-in-the-loop** — all outputs are reports/suggestions, not auto-executed changes
3. **Plain Python** — no heavy frameworks, every line is yours to debug and modify

## Next Steps

1. **Phase 1:** Run `python main.py --mode report` manually for a week. Review the Markdown reports.
2. **Phase 2:** Verify that follow-up suggestions appear in API responses (already wired).
3. **Phase 3:** Review investigation reports when anomalies trigger.
4. **Phase 4:** Based on gap reports, manually add missing metrics to `semantic_layer.yaml`.
5. **Phase 5:** (Future) Replace alert agent's rule-based logic with LLM reasoning using the same ReAct framework.
