-- ============================================================
-- DUCKDB BASELINE TABLES
-- Run this in DuckDB to create pre-calculated summary tables.
-- These enable instant baseline lookup in the Text-to-SQL API.
-- ============================================================

-- -----------------------------------------------------------
-- Daily summary table (mirror of Informix fact_txn_daily_summary)
-- Populate this from your Informix ETL or with sample data.
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_txn_daily_summary (
    summary_date      INTEGER,
    server_sk         INTEGER,
    device_category   VARCHAR,
    hour24            SMALLINT,
    txn_count         INTEGER,
    approved_count    INTEGER,
    stuck_count       INTEGER,
    reversed_count    INTEGER,
    offline_count     INTEGER,
    hot_card_count    INTEGER,
    error_count       INTEGER,
    total_amount      DECIMAL(18,2),
    avg_switch_ms     INTEGER,
    max_switch_ms     INTEGER,
    avg_completion_ms INTEGER,
    max_completion_ms INTEGER,
    terminal_risk_avg INTEGER,

    -- Baseline enrichment columns
    prev_day_txn_count    INTEGER,
    prev_week_txn_count   INTEGER,
    avg_7d_txn_count      DECIMAL(18,2),

    load_timestamp    TIMESTAMP
);

-- Primary lookup index
CREATE INDEX IF NOT EXISTS idx_summary_lookup 
ON fact_txn_daily_summary(summary_date, server_sk, device_category, hour24);

-- -----------------------------------------------------------
-- SLA Threshold Configuration
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS metric_sla_thresholds (
    metric_name         VARCHAR PRIMARY KEY,
    sla_min_value       DECIMAL(18,4),
    sla_max_value       DECIMAL(18,4),
    description         VARCHAR
);

-- Default thresholds
INSERT OR REPLACE INTO metric_sla_thresholds VALUES 
('txn_count', 10000, NULL, 'Daily transaction count per server/device/hour'),
('approval_rate', 95.0, 100.0, 'Approval percentage — below 95% is SLA breach'),
('total_amount', NULL, NULL, 'Total monetary amount'),
('avg_switch_ms', NULL, 500, 'Average switch latency in ms — above 500ms is SLA breach'),
('stuck_count', NULL, 50, 'Stuck transaction count — above 50 is concern'),
('hot_card_count', NULL, 10, 'Hot card count — above 10 requires investigation'),
('error_count', NULL, 100, 'Error transaction count — above 100 is SLA breach');

-- -----------------------------------------------------------
-- SAMPLE DATA (for testing without Informix connection)
-- Remove these inserts when loading real data.
-- -----------------------------------------------------------
INSERT INTO fact_txn_daily_summary 
(summary_date, server_sk, device_category, hour24, txn_count, approved_count, 
 stuck_count, avg_switch_ms, prev_day_txn_count, prev_week_txn_count, avg_7d_txn_count)
VALUES
(20250812, 1, 'ATM', 9, 15000, 14850, 3, 120, 16200, 15500, 15800),
(20250812, 1, 'POS', 9, 8200, 8100, 1, 95, 8500, 8300, 8400),
(20250812, 2, 'ATM', 9, 12000, 11800, 5, 180, 15000, 14000, 14500),
(20250812, 2, 'POS', 9, 6000, 5940, 2, 110, 6500, 6200, 6300),
(20250811, 1, 'ATM', 9, 16200, 16000, 2, 115, 15500, 15800, 15600),
(20250811, 1, 'POS', 9, 8500, 8420, 1, 98, 8200, 8400, 8350),
(20250811, 2, 'ATM', 9, 15000, 14800, 4, 175, 14500, 14200, 14800),
(20250811, 2, 'POS', 9, 6500, 6435, 1, 105, 6300, 6400, 6450);
