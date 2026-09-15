# Alert Agent Module

## What It Does

A lightweight monitoring agent that reads your pre-computed baseline table every 15 minutes, detects anomalies, decides whether to alert, and sends notifications.

## Architecture

```
Every 15 minutes:
  1. Query baseline table for unalerted anomalies
  2. Check maintenance windows (suppress if in maintenance)
  3. Apply rule-based objective definer:
     - SLA breach → HIGH alert (#ops-critical)
     - Z-score > 3.0 → MEDIUM alert (#ops-alerts)
     - Z-score 1.5-3.0 → LOW alert (#daily-summary)
     - Maintenance window → SUPPRESS
  4. Send alert via Slack (or console fallback)
  5. Log decision to alert_log table for future learning
```

## Run

### Option 1: With APScheduler (recommended)

```bash
pip install apscheduler
python agent/main.py
```

### Option 2: With schedule library

```bash
pip install schedule
python agent/main.py
```

### Option 3: Simple sleep loop (no dependencies)

```bash
python agent/main.py
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_DB_PATH` | `data/warehouse.db` | Path to DuckDB/SQLite database |
| `SLACK_WEBHOOK_URL` | `None` | Slack webhook URL. If not set, prints to console |
| `AGENT_INTERVAL_MIN` | `15` | Check interval in minutes |

## Example

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
export AGENT_DB_PATH="data/warehouse.db"
python agent/main.py
```

## Files

| File | Purpose |
|------|---------|
| `main.py` | Scheduler runner (APScheduler → schedule → sleep fallback) |
| `agent_loop.py` | Main ReAct loop: observe → decide → act → log |
| `objective_definer.py` | Rule-based decision engine |
| `tools/query_baseline.py` | Read anomaly rows from baseline table |
| `tools/check_maintenance.py` | Check if server is in maintenance window |
| `tools/send_alert.py` | Synthesize and send alert message |
| `notifiers/slack_adapter.py` | Slack webhook adapter |

## Future Upgrade Path

Phase 1 (now): Rule-based objective definer  
Phase 2 (later): Replace `objective_definer.py` with LLM-based reasoning  
Phase 3 (later): Add correlation tools, multi-metric analysis  

The architecture is ready. Just swap the definer.
