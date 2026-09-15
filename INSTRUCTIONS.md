# Ultimate Text-to-SQL v2.2 — Final Edition
## Integration Guide: Zero-Mem + Simplified Baseline Enrichment

### What This Package Contains

1. **Zero-Mem**: Lightweight deterministic memory layer (SQLite, no LLM)
2. **Simplified Baseline Enrichment**: ONE query to pre-calculated table instead of 6 ad-hoc SQLs

---

### Architecture

```
User Query
    |
    v
[SQLite Memory]  <-- reads history (<50ms, no LLM)
    |
    v
Intent Extractor (LLM)  <-- with memory context
    |
    v
Context Builder → SQL Generator → SQL Reviewer → Validator
    |
    v
DuckDB Execution
    |
    v
[Baseline Enricher]  <-- ONE lookup query (<50ms, no LLM)
    |                    Queries fact_txn_daily_summary (if exists)
    |                    Falls back to result-based computation
    |
    v
Dual Synthesizer (LLM)  <-- with baseline context
    |
    v
[SQLite Memory]  <-- saves raw record
    |
    v
Response (with context + anomaly flags)
```

---

### Files Added/Modified

```
src/
├── ports/
│   └── memory_store_port.py              # NEW: memory contract
├── adapters/
│   └── sqlite_memory_adapter.py        # NEW: SQLite memory engine
├── core/
│   ├── memory_intent_extractor.py      # NEW: memory-aware intent
│   ├── memory_orchestrator.py          # NEW: memory-aware orchestrator
│   ├── baseline_models.py              # NEW: BaselineMetrics dataclass
│   ├── baseline_enricher.py            # NEW: simplified baseline engine
│   ├── baseline_synthesizer.py         # NEW: synthesizer with baseline
│   └── enriched_orchestrator.py        # NEW: integrated orchestrator
├── api/
│   └── main_enriched.py                # NEW: entry point
└── sql/
    └── create_baseline_tables_duckdb.sql  # NEW: DuckDB baseline schema + sample data

prompts/
├── ceo_system_baseline.md              # NEW: CEO prompt with baseline
└── ba_system_baseline.md               # NEW: BA prompt with baseline

INSTRUCTIONS.md                         # This file
```

---

### Integration Steps

#### Step 1: Ensure `data/` directory exists

```bash
mkdir -p data
```

#### Step 2: Create baseline tables in DuckDB (for testing)

```bash
# Run the SQL to create baseline tables with sample data
duckdb data/warehouse.db < sql/create_baseline_tables_duckdb.sql
```

For production, populate `fact_txn_daily_summary` from your Informix ETL instead of using sample data.

#### Step 3: No new Python dependencies

- `sqlite3` is built into Python
- Baseline enricher reuses existing `DuckDBExecutor`
- No `pip install` needed

#### Step 4: Run

```bash
uvicorn src.api.main_enriched:app --reload
```

---

### How Baseline Enrichment Works (Simplified)

**Old approach (replaced):** 6 separate SQL queries, string replacement, fragile
**New approach:** ONE indexed lookup to `fact_txn_daily_summary`

```python
# After user query executes:
baseline = baseline_enricher.enrich(intent, generated_sql, execution_result)

# Strategy 1: If fact_txn_daily_summary exists in DuckDB
#   → Single indexed lookup: SELECT prev_day, prev_week, avg_7d 
#   → <50ms, zero LLM tokens

# Strategy 2: If table doesn't exist (fallback)
#   → Compute from result rows (for time-series queries)
#   → Still zero LLM tokens
```

---

### What Gets Computed

| Comparison | Source | Example Output |
|------------|--------|----------------|
| vs Yesterday | `prev_day_txn_count` column | "Today 12K, yesterday 15K (-20%)" |
| vs Last Week | `prev_week_txn_count` column | "Today 12K, last week 14K (-14%)" |
| vs 7-Day Avg | `avg_7d_txn_count` column | "7-day avg 13.5K (-11%)" |
| SLA Breach | `metric_sla_thresholds` table | "Below SLA minimum of 10K" |
| Anomaly | Deviation from 7-day avg | "⚠️ Medium anomaly: 30% deviation" |

---

### DuckDB Schema for Baseline

```sql
-- Pre-calculated daily summary (populate from Informix ETL)
CREATE TABLE fact_txn_daily_summary (
    summary_date      INTEGER,      -- YYYYMMDD
    server_sk         INTEGER,
    device_category   VARCHAR,
    hour24            SMALLINT,
    txn_count         INTEGER,
    approved_count    INTEGER,
    stuck_count       INTEGER,
    avg_switch_ms     INTEGER,
    prev_day_txn_count    INTEGER,  -- pre-computed by ETL
    prev_week_txn_count   INTEGER,  -- pre-computed by ETL
    avg_7d_txn_count      DECIMAL   -- pre-computed by ETL
);

-- SLA thresholds (editable)
CREATE TABLE metric_sla_thresholds (
    metric_name    VARCHAR PRIMARY KEY,
    sla_min_value  DECIMAL,
    sla_max_value  DECIMAL
);
```

---

### Production ETL Flow (Informix → DuckDB)

```bash
# Nightly cron at 2:05 AM (after Informix sp_nightly_txn_summary)

# 1. Export from Informix
dbaccess yourdb - <<EOF > /tmp/daily_summary.csv
UNLOAD TO '/tmp/daily_summary.unl'
SELECT summary_date, server_sk, device_category, hour24,
       txn_count, approved_count, stuck_count, avg_switch_ms,
       prev_day_txn_count, prev_week_txn_count, avg_7d_txn_count
FROM fact_txn_daily_summary
WHERE summary_date = TODAY - 1;
EOF

# 2. Load into DuckDB
duckdb data/warehouse.db -c "
  CREATE TEMP TABLE tmp AS SELECT * FROM read_csv('/tmp/daily_summary.csv');
  INSERT OR REPLACE INTO fact_txn_daily_summary SELECT * FROM tmp;
"
```

---

### Example: Before vs After

#### Before (v2.0 — raw data only)

> **CEO**: "SW02 processed 12,000 transactions today."
>
> **User**: *"Is that good? Bad? Normal?"*

#### After (v2.2 — with baseline)

> **CEO**: "SW02 processed 12,000 transactions today. **20% below yesterday (15K) and 11% below 7-day average (13.5K).** Still above SLA minimum of 10K. No anomaly flagged."
>
> **User**: *"I know the context immediately."*

---

### API Endpoints

```bash
# Health check
curl http://localhost:8000/health
# → {"status": "ok", "version": "v2.2-enriched", "features": ["zero-mem", "baseline-enrichment"]}

# Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"text": "total transactions today", "user_id": "user_001"}'

# Debug: view user memory
curl http://localhost:8000/memory/user_001
```

---

### Performance Summary

| Layer | Time | LLM Tokens | Value |
|-------|------|------------|-------|
| Zero-Mem read | ~15-50ms | 0 | Session continuity |
| Intent extraction | ~500-1500ms | ~500 | Understanding |
| SQL generation | ~10ms | 0 | Deterministic |
| SQL review | ~800-2000ms | ~800 | Safety gate |
| Execution | ~50-200ms | 0 | Data retrieval |
| **Baseline enrichment** | **~10-50ms** | **0** | **Historical context** |
| Synthesis | ~800-1500ms | ~600 | Answer generation |
| Zero-Mem write | ~2ms | 0 | Persistence |
| **Total** | **~2-5s** | **~1900** | **Full context** |

---

### Rollback

To disable features:
- **Disable baseline only**: Drop `fact_txn_daily_summary` from DuckDB. System falls back to raw data.
- **Disable memory only**: Revert to `src/api/main.py`. Memory layer is completely additive.
- **Disable both**: Use original `main.py` from v2.0.

---

### Notes

- **Baseline requires pre-calculated data**: If `fact_txn_daily_summary` is empty, baseline falls back to result-based computation (time-series only).
- **Sample data included**: `sql/create_baseline_tables_duckdb.sql` has sample rows for immediate testing.
- **SQLite single-file**: For multi-instance deployments, migrate memory store to PostgreSQL.
- **No existing files modified**: All new files are additive. Original codebase untouched.
