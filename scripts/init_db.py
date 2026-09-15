import os
import duckdb


def init():
    os.makedirs("data", exist_ok=True)
    path = "data/bank.duckdb"
    if os.path.exists(path):
        os.remove(path)
    con = duckdb.connect(path)

    # -----------------------------------------------------------
    # DIMENSION TABLES
    # -----------------------------------------------------------
    con.execute("""
        CREATE TABLE dim_date (
            date_sk INTEGER PRIMARY KEY,
            full_date DATE NOT NULL,
            year SMALLINT,
            quarter SMALLINT,
            month SMALLINT,
            month_name VARCHAR(9),
            day_of_month SMALLINT,
            day_of_week SMALLINT,
            day_name VARCHAR(9),
            week_of_year SMALLINT,
            is_weekend SMALLINT,
            is_holiday SMALLINT,
            holiday_name VARCHAR(50)
        )
    """)

    con.execute("""
        CREATE TABLE dim_time (
            time_sk INTEGER PRIMARY KEY,
            hour24 SMALLINT,
            hour12 SMALLINT,
            minute SMALLINT,
            second SMALLINT,
            am_pm CHAR(2),
            time_of_day VARCHAR(8)
        )
    """)

    con.execute("""
        CREATE TABLE dim_status (
            status_sk INTEGER PRIMARY KEY,
            status_code INTEGER,
            hot_flag SMALLINT,
            offline_flag SMALLINT,
            rev_flag SMALLINT,
            lifecycle_stage VARCHAR(20),
            is_hot_card SMALLINT,
            is_offline SMALLINT,
            is_reversal SMALLINT,
            is_completed SMALLINT
        )
    """)

    con.execute("""
        CREATE TABLE dim_server (
            server_sk INTEGER PRIMARY KEY,
            server_name VARCHAR(50) NOT NULL,
            server_type VARCHAR(20),
            location VARCHAR(50)
        )
    """)

    con.execute("""
        CREATE TABLE dim_terminal (
            terminal_sk INTEGER PRIMARY KEY,
            devicetype SMALLINT,
            pos_entry_mode SMALLINT,
            pos_cond_code SMALLINT,
            pos_data_code CHAR(12),
            term_con_type SMALLINT,
            term_mac_use SMALLINT,
            term_enc_type SMALLINT,
            term_enc_meth SMALLINT,
            device_category VARCHAR(20),
            entry_mode_desc VARCHAR(20),
            is_unknown_entry SMALLINT,
            is_magstripe SMALLINT,
            is_chip SMALLINT,
            is_key_entry SMALLINT,
            is_pan_auto SMALLINT,
            is_cnp SMALLINT,
            terminal_risk_score SMALLINT
        )
    """)

    con.execute("""
        CREATE TABLE dim_error (
            error_sk INTEGER PRIMARY KEY,
            err_severity SMALLINT,
            err_indicator SMALLINT,
            err_bitno SMALLINT,
            err_subbitno SMALLINT,
            error_description VARCHAR(100)
        )
    """)

    # -----------------------------------------------------------
    # FACT TABLE
    # -----------------------------------------------------------
    con.execute("""
        CREATE TABLE fact_transaction (
            transaction_sk BIGINT PRIMARY KEY,
            ser_pk BIGINT NOT NULL,
            trace INTEGER,
            sys_trace INTEGER,
            sys_batch INTEGER,
            refnum CHAR(15),
            otrace INTEGER,
            orefnum CHAR(15),
            msgno INTEGER,
            date_in_sk INTEGER NOT NULL,
            time_in_sk INTEGER NOT NULL,
            date_out_sk INTEGER,
            time_out_sk INTEGER,
            date_trans_sk INTEGER,
            time_trans_sk INTEGER,
            date_cap_sk INTEGER,
            date_stl_sk INTEGER,
            date_conv_sk INTEGER,
            date_abm_sk INTEGER,
            time_abm_sk INTEGER,
            date_otr_sk INTEGER,
            time_otr_sk INTEGER,
            date_odate_sk INTEGER,
            time_otime_sk INTEGER,
            status_sk INTEGER NOT NULL,
            server_sk INTEGER NOT NULL,
            terminal_sk INTEGER,
            error_sk INTEGER,
            txnamt DECIMAL(18,2),
            switch_latency_ms INTEGER,
            completion_latency_ms INTEGER,
            is_approved SMALLINT,
            is_stuck SMALLINT,
            is_reversed SMALLINT,
            is_offline SMALLINT,
            is_hot_card SMALLINT,
            has_error SMALLINT,
            terminal_risk_score SMALLINT
        )
    """)

    # -----------------------------------------------------------
    # POPULATE dim_date (last 30 days)
    # -----------------------------------------------------------
    from datetime import date, timedelta
    today = date(2026, 8, 12)  # fixed for reproducible tests
    dates = []
    for i in range(-5, 5):
        d = today + timedelta(days=i)
        sk = int(d.strftime("%Y%m%d"))
        dates.append((
            sk, d, d.year, (d.month - 1) // 3 + 1, d.month,
            d.strftime("%B"), d.day, d.weekday() + 1, d.strftime("%A"),
            d.isocalendar()[1], 1 if d.weekday() >= 5 else 0, 0, None
        ))
    con.executemany("""
        INSERT INTO dim_date VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, dates)

    # -----------------------------------------------------------
    # POPULATE dim_time (all 86400 seconds)
    # -----------------------------------------------------------
    times = []
    for sec in range(86400):
        hh = sec // 3600
        mm = (sec % 3600) // 60
        ss = sec % 60
        h12 = 12 if hh % 12 == 0 else hh % 12
        ampm = 'AM' if hh < 12 else 'PM'
        if 5 <= hh <= 11:
            tod = 'Morning'
        elif 12 <= hh <= 16:
            tod = 'Afternoon'
        elif 17 <= hh <= 20:
            tod = 'Evening'
        else:
            tod = 'Night'
        times.append((sec, hh, h12, mm, ss, ampm, tod))
    con.executemany("""
        INSERT INTO dim_time VALUES (?, ?, ?, ?, ?, ?, ?)
    """, times)

    # -----------------------------------------------------------
    # POPULATE dim_status
    # -----------------------------------------------------------
    statuses = [
        (1, 0, 0, 0, 0, 'Completed', 0, 0, 0, 1),
        (2, 0, 1, 0, 0, 'Hot Card', 1, 0, 0, 0),
        (3, 1110, 0, 0, 0, 'Stuck', 0, 0, 0, 0),
        (4, 0, 0, 1, 0, 'Offline', 0, 1, 0, 0),
        (5, 0, 0, 0, 1, 'Reversal', 0, 0, 1, 0),
    ]
    con.executemany("""
        INSERT INTO dim_status (status_sk, status_code, hot_flag, offline_flag, rev_flag,
            lifecycle_stage, is_hot_card, is_offline, is_reversal, is_completed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, statuses)

    # -----------------------------------------------------------
    # POPULATE dim_server
    # -----------------------------------------------------------
    servers = [
        (1, 'SRV-A', 'Primary', 'Datacenter-East'),
        (2, 'SRV-B', 'Primary', 'Datacenter-West'),
        (3, 'SRV-C', 'Backup', 'Datacenter-East'),
        (4, 'SRV-D', 'Backup', 'Datacenter-West'),
    ]
    con.executemany("""
        INSERT INTO dim_server (server_sk, server_name, server_type, location)
        VALUES (?, ?, ?, ?)
    """, servers)

    # -----------------------------------------------------------
    # POPULATE dim_terminal
    # -----------------------------------------------------------
    terminals = [
        (1, 1, 1, 1, '123456789012', 1, 1, 1, 1, 'ATM', 'Magstripe', 0, 1, 0, 0, 0, 0, 2),
        (2, 2, 5, 2, '987654321098', 2, 1, 2, 1, 'POS', 'Chip', 0, 0, 1, 0, 0, 0, 1),
        (3, 3, 1, 1, '111111111111', 1, 1, 1, 1, 'ATM', 'Magstripe', 0, 1, 0, 0, 0, 0, 3),
        (4, 4, 7, 3, '222222222222', 3, 2, 3, 2, 'Mobile', 'CNP', 0, 0, 0, 0, 1, 1, 4),
    ]
    con.executemany("""
        INSERT INTO dim_terminal (
            terminal_sk, devicetype, pos_entry_mode, pos_cond_code, pos_data_code,
            term_con_type, term_mac_use, term_enc_type, term_enc_meth,
            device_category, entry_mode_desc, is_unknown_entry, is_magstripe,
            is_chip, is_key_entry, is_pan_auto, is_cnp, terminal_risk_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, terminals)

    # -----------------------------------------------------------
    # POPULATE dim_error
    # -----------------------------------------------------------
    errors = [
        (1, 1, 1, 1, 1, 'Timeout'),
        (2, 2, 2, 2, 2, 'Invalid PIN'),
        (3, 3, 1, 3, 1, 'Network Error'),
    ]
    con.executemany("""
        INSERT INTO dim_error (error_sk, err_severity, err_indicator, err_bitno, err_subbitno, error_description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, errors)

    # -----------------------------------------------------------
    # POPULATE fact_transaction
    # -----------------------------------------------------------
    import random
    random.seed(42)

    # Get SKs
    date_sks = [r[0] for r in con.execute("SELECT date_sk FROM dim_date ORDER BY date_sk").fetchall()]
    status_sks = [r[0] for r in con.execute("SELECT status_sk FROM dim_status").fetchall()]
    server_sks = [r[0] for r in con.execute("SELECT server_sk FROM dim_server").fetchall()]
    terminal_sks = [r[0] for r in con.execute("SELECT terminal_sk FROM dim_terminal").fetchall()]
    error_sks = [r[0] for r in con.execute("SELECT error_sk FROM dim_error").fetchall()]

    facts = []
    for i in range(1, 101):
        dsk = random.choice(date_sks)
        tsk = random.randint(0, 86399)
        ssk = random.choice(status_sks)
        srv_sk = random.choice(server_sks)
        ter_sk = random.choice(terminal_sks + [None])
        err_sk = random.choice(error_sks + [None])
        amt = round(random.uniform(10, 5000), 2)
        switch_lat = random.randint(50, 2000)
        comp_lat = random.randint(100, 5000)
        appr = 1 if random.random() > 0.15 else 0
        stuck = 1 if random.random() > 0.95 else 0
        rev = 1 if random.random() > 0.98 else 0
        off = 1 if random.random() > 0.90 else 0
        hot = 1 if random.random() > 0.97 else 0
        has_err = 1 if err_sk is not None else 0
        risk = random.randint(1, 5) if ter_sk else None

        facts.append((
            i, i * 1000, i, i, i, f"REF{i:06d}", i, f"OREF{i:06d}", i,
            dsk, tsk, dsk, tsk, dsk, tsk, dsk, dsk, None, None, None,
            None, None, None, None, ssk, srv_sk, ter_sk, err_sk,
            amt, switch_lat, comp_lat, appr, stuck, rev, off, hot, has_err, risk
        ))

    con.executemany("""
        INSERT INTO fact_transaction VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
    """, facts)

    # -----------------------------------------------------------
    # BASELINE TABLES (for enrichment feature)
    # -----------------------------------------------------------
    con.execute("""
        CREATE TABLE IF NOT EXISTS fact_txn_daily_summary (
            summary_date INTEGER,
            server_sk INTEGER,
            device_category VARCHAR,
            hour24 SMALLINT,
            txn_count INTEGER,
            approved_count INTEGER,
            stuck_count INTEGER,
            reversed_count INTEGER,
            offline_count INTEGER,
            hot_card_count INTEGER,
            error_count INTEGER,
            total_amount DECIMAL(18,2),
            avg_switch_ms INTEGER,
            max_switch_ms INTEGER,
            avg_completion_ms INTEGER,
            max_completion_ms INTEGER,
            terminal_risk_avg INTEGER,
            prev_day_txn_count INTEGER,
            prev_week_txn_count INTEGER,
            avg_7d_txn_count DECIMAL(18,2),
            load_timestamp TIMESTAMP
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS metric_sla_thresholds (
            metric_name VARCHAR PRIMARY KEY,
            sla_min_value DECIMAL(18,4),
            sla_max_value DECIMAL(18,4),
            description VARCHAR
        )
    """)

    # Insert default SLA thresholds
    con.execute("""
        INSERT OR REPLACE INTO metric_sla_thresholds VALUES
        ('txn_count', 10000, NULL, 'Daily transaction count per server/device/hour'),
        ('approval_rate', 95.0, 100.0, 'Approval percentage — below 95% is SLA breach'),
        ('total_amount', NULL, NULL, 'Total monetary amount'),
        ('avg_switch_ms', NULL, 500, 'Average switch latency in ms — above 500ms is SLA breach'),
        ('stuck_count', NULL, 50, 'Stuck transaction count — above 50 is concern'),
        ('hot_card_count', NULL, 10, 'Hot card count — above 10 requires investigation'),
        ('error_count', NULL, 100, 'Error transaction count — above 100 is SLA breach')
    """)

    # Insert sample baseline data (matching the 2026-08-12 fixed date)
    # Get server SKs
    srv_rows = con.execute("SELECT server_sk, server_name FROM dim_server").fetchall()
    srv_map = {name: sk for sk, name in srv_rows}

    sample_baselines = [
        (20260812, srv_map.get('SRV-A'), 'ATM', 9, 15000, 14850, 3, 120, 16200, 15500, 15800),
        (20260812, srv_map.get('SRV-A'), 'POS', 9, 8200, 8100, 1, 95, 8500, 8300, 8400),
        (20260812, srv_map.get('SRV-B'), 'ATM', 9, 12000, 11800, 5, 180, 15000, 14000, 14500),
        (20260812, srv_map.get('SRV-B'), 'POS', 9, 6000, 5940, 2, 110, 6500, 6200, 6300),
        (20260811, srv_map.get('SRV-A'), 'ATM', 9, 16200, 16000, 2, 115, 15500, 15800, 15600),
        (20260811, srv_map.get('SRV-A'), 'POS', 9, 8500, 8420, 1, 98, 8200, 8400, 8350),
        (20260811, srv_map.get('SRV-B'), 'ATM', 9, 15000, 14800, 4, 175, 14500, 14200, 14800),
        (20260811, srv_map.get('SRV-B'), 'POS', 9, 6500, 6435, 1, 105, 6300, 6400, 6450),
    ]

    con.executemany("""
        INSERT INTO fact_txn_daily_summary
        (summary_date, server_sk, device_category, hour24, txn_count, approved_count,
         stuck_count, avg_switch_ms, prev_day_txn_count, prev_week_txn_count, avg_7d_txn_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_baselines)

    con.close()
    print(f"Star schema + baseline tables initialized at {path}")
    print(f"  dim_date: {len(date_sks)} rows")
    print(f"  dim_time: 86400 rows")
    print(f"  dim_status: 5 rows")
    print(f"  dim_server: 4 rows")
    print(f"  dim_terminal: 4 rows")
    print(f"  dim_error: 3 rows")
    print(f"  fact_transaction: 100 rows")


if __name__ == "__main__":
    init()
