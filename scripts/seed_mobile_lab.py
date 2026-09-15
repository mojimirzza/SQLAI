#!/usr/bin/env python3
"""Prepare a mobile-friendly, current-date DuckDB lab dataset.

This is additive and intended for demo/test environments. It keeps the original
frozen Stage-4 database initializer intact, then adds current dates, sample
transactions, and the baseline table expected by the alert agent.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
import random

import duckdb

DB_PATH = os.environ.get("DUCKDB_PATH", "data/bank.duckdb")
DAYS = int(os.environ.get("MOBILE_LAB_DAYS", "35"))


def main() -> None:
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"Database not found: {DB_PATH}. Run scripts/init_db.py first.")

    con = duckdb.connect(DB_PATH)
    today = date.today()
    start = today - timedelta(days=DAYS - 1)

    # Extend calendar for current relative-date questions.
    for i in range(DAYS):
        d = start + timedelta(days=i)
        sk = int(d.strftime("%Y%m%d"))
        con.execute("""
            INSERT INTO dim_date
            SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            WHERE NOT EXISTS (SELECT 1 FROM dim_date WHERE date_sk = ?)
        """, [
            sk, d, d.year, (d.month - 1) // 3 + 1, d.month,
            d.strftime("%B"), d.day, d.weekday() + 1, d.strftime("%A"),
            d.isocalendar()[1], 1 if d.weekday() >= 5 else 0, 0, None, sk
        ])

    # Current-date transaction sample with deliberate anomaly on SRV-A.
    rng = random.Random(20260907)
    max_id = con.execute("SELECT COALESCE(MAX(transaction_sk),0) FROM fact_transaction").fetchone()[0]
    rows = []
    for i in range(1, DAYS * 40 + 1):
        d = start + timedelta(days=(i - 1) % DAYS)
        dsk = int(d.strftime("%Y%m%d"))
        tsk = rng.randint(0, 86399)
        srv = 1 if (i % 3 == 0) else rng.choice([1,2,3,4])
        latency = rng.randint(70, 350)
        if d == today and srv == 1:
            latency = rng.randint(700, 1500)
        rows.append((
            max_id+i, (max_id+i)*1000, max_id+i, max_id+i, max_id+i,
            f"MLAB{max_id+i:08d}", max_id+i, f"OMLAB{max_id+i:08d}", max_id+i,
            dsk, tsk, dsk, tsk, dsk, tsk, dsk, dsk, None, None, None,
            None, None, None, None, 1, srv, rng.choice([1,2,3,4,None]),
            rng.choice([1,2,3,None]), rng.uniform(10,5000), latency,
            rng.randint(100,5000), 1 if latency < 900 else 0,
            1 if latency > 1100 else 0, 0, 0, 0, 1 if latency > 900 else 0,
            rng.randint(1,5)
        ))

    con.executemany("INSERT INTO fact_transaction VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)

    con.execute("""
        CREATE TABLE IF NOT EXISTS metric_daily_baseline (
            baseline_date INTEGER NOT NULL,
            metric_name VARCHAR NOT NULL,
            server_sk INTEGER,
            device_category VARCHAR,
            hour24 SMALLINT,
            current_value DOUBLE,
            yest_value DOUBLE,
            yest_delta_pct DOUBLE,
            avg_7d_value DOUBLE,
            avg_7d_delta_pct DOUBLE,
            z_score DOUBLE,
            is_anomaly SMALLINT DEFAULT 0,
            anomaly_severity VARCHAR,
            is_sla_breach SMALLINT DEFAULT 0,
            sla_min_value DOUBLE,
            sla_max_value DOUBLE,
            alerted SMALLINT DEFAULT 0
        )
    """)

    # One unmistakable current anomaly plus a normal comparison row.
    today_sk = int(today.strftime("%Y%m%d"))
    yesterday_sk = int((today - timedelta(days=1)).strftime("%Y%m%d"))
    con.execute("DELETE FROM metric_daily_baseline WHERE baseline_date = ?", [today_sk])
    con.executemany("""
        INSERT INTO metric_daily_baseline VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [
        (today_sk, "avg_switch_ms", 1, "ATM", 9, 980.0, 320.0, 206.25, 345.0, 184.06, 5.8, 1, "high", 1, None, 500.0, 0),
        (today_sk, "approval_rate", 1, "ATM", 9, 91.0, 98.0, -7.14, 97.0, -6.19, -3.7, 1, "medium", 1, 95.0, 100.0, 0),
        (yesterday_sk, "avg_switch_ms", 1, "ATM", 9, 320.0, 305.0, 4.92, 340.0, -5.88, 0.2, 0, "none", 0, None, 500.0, 0),
    ])
    con.close()
    print(f"Mobile lab seeded: {DB_PATH}; current demo date={today_sk}; rows added={len(rows)}")

if __name__ == "__main__":
    main()
