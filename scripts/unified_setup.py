#!/usr/bin/env python3
"""
Unified Setup Script
Initializes all databases and verifies the complete system.
Run once after cloning or after schema changes.
"""
import os
import sys
import sqlite3

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

print("=" * 60)
print("UNIFIED SYSTEM SETUP")
print("=" * 60)

# 1. Initialize main project databases
print("\n[1/5] Initializing main project databases...")
try:
    import subprocess
    result = subprocess.run([sys.executable, "scripts/init_db.py"], capture_output=True, text=True)
    if result.returncode == 0:
        print("  ✓ Main databases initialized")
    else:
        print(f"  ✗ Error: {result.stderr}")
        sys.exit(1)
except Exception as e:
    print(f"  ✗ Failed: {e}")
    sys.exit(1)

# 2. Initialize the SQLite memory database used by the enriched API
print("\n[2/5] Initializing memory database (memory.db)...")
try:
    sys.path.insert(0, os.path.abspath("."))
    sys.path.insert(0, os.path.abspath("src"))
    from adapters.sqlite_memory_adapter import SQLiteMemoryAdapter
    SQLiteMemoryAdapter("data/memory.db")
    print("  ✓ Memory database ready")
except Exception as e:
    print(f"  ✗ Memory database initialization failed: {e}")
    sys.exit(1)

# 3. Initialize alert agent database
print("\n[3/5] Initializing alert agent database (agent_alerts.db)...")
alert_db = "data/agent_alerts.db"
with sqlite3.connect(alert_db) as conn:
    conn.execute("""
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
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_time ON alert_log(triggered_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alert_metric ON alert_log(metric_name, triggered_at)")
    conn.commit()
print("  ✓ Alert agent database ready")

# 4. Initialize sidecar database
print("\n[4/5] Initializing sidecar database (agent_state.db)...")
state_db = "data/agent_state.db"
with sqlite3.connect(state_db) as conn:
    conn.execute("""
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
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS followup_suggestions (
            id TEXT PRIMARY KEY,
            query_id TEXT NOT NULL,
            session_id TEXT,
            suggestions_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            user_clicked INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gap_reports (
            id TEXT PRIMARY KEY,
            report_date TEXT NOT NULL,
            report_path TEXT NOT NULL,
            missing_metrics_json TEXT,
            missing_dimensions_json TEXT,
            generated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_runs (
            id TEXT PRIMARY KEY,
            agent_name TEXT NOT NULL,
            mode TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            success INTEGER DEFAULT 0,
            output_summary TEXT,
            trace_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_correlations (
            id TEXT PRIMARY KEY,
            investigation_id TEXT,
            alert_id TEXT,
            metric_name TEXT,
            correlation_type TEXT,
            confidence REAL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
print("  ✓ Sidecar database ready")

# 5. Verify file structure
print("\n[5/5] Verifying file structure...")
required = [
    "src/core/enriched_orchestrator.py",
    "src/core/sidecar_bridge.py",
    "agent/main.py",
    "sidecar/main.py",
    "sidecar/config.yaml",
    "data/bank.duckdb",
    "data/memory.db",
    "data/agent_alerts.db",
    "data/agent_state.db",
]
all_ok = True
for f in required:
    exists = os.path.exists(f)
    status = "✓" if exists else "✗"
    print(f"  {status} {f}")
    if not exists:
        all_ok = False

print("\n" + "=" * 60)
if all_ok:
    print("SETUP COMPLETE. All systems ready.")
    print("\nNext steps:")
    print("  1. Set OPENAI_API_KEY in .env")
    print("  2. Run: python run.py")
    print("  3. In another terminal: python agent/main.py")
    print("  4. For sidecar: cd sidecar && python main.py --mode report")
else:
    print("SETUP INCOMPLETE. Missing files detected.")
    sys.exit(1)
print("=" * 60)
