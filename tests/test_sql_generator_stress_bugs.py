from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from core.models import Intent
from core.sql_generator import SQLGenerator
from adapters.yaml_semantic_adapter import YAMLSemanticAdapter


@pytest.fixture()
def generator():
    return SQLGenerator(YAMLSemanticAdapter(str(ROOT / "src/config/semantic_layer.yaml")))


def test_bug1_filter_dimension_join_is_auto_added_from_semantic_layer(generator):
    intent = Intent(
        category="approval_rate",
        confidence=0.99,
        query_type="aggregate",
        entities={"err_severity": 1},
    )
    generated = generator.generate(intent, {})
    sql = generated.sql
    assert "dim_error.err_severity = 1" in sql
    assert "LEFT JOIN dim_error ON dim_error.error_sk = fact_transaction.error_sk" in sql




def test_bug1_exact_server_and_device_filters_auto_add_both_dimension_joins(generator):
    intent = Intent(
        category="total_transactions",
        confidence=0.99,
        query_type="aggregate",
        entities={"server_name": "SRV-A", "device_category": "ATM"},
    )
    sql = generator.generate(intent, {}).sql
    assert "dim_server.server_name = 'SRV-A'" in sql
    assert "dim_terminal.device_category = 'ATM'" in sql
    assert "INNER JOIN dim_server ON dim_server.server_sk = fact_transaction.server_sk" in sql
    assert "LEFT JOIN dim_terminal ON dim_terminal.terminal_sk = fact_transaction.terminal_sk" in sql

def test_bug2_time_of_day_uses_dim_time_hour24_not_surrogate_seconds(generator):
    intent = Intent(
        category="total_transactions",
        confidence=0.99,
        query_type="aggregate",
        entities={"time_of_day": "morning"},
    )
    sql = generator.generate(intent, {}).sql
    assert "dim_time.hour24 >= 5 AND dim_time.hour24 <= 11" in sql
    assert "fact_transaction.time_in_sk >= 18000" not in sql
    assert "INNER JOIN dim_time" in sql


@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("is_approved", True, "fact_transaction.is_approved = 1"),
        ("is_approved", False, "fact_transaction.is_approved = 0"),
        ("has_error", True, "fact_transaction.has_error = 1"),
        ("is_stuck", True, "fact_transaction.is_stuck = 1"),
        ("is_hot_card", False, "fact_transaction.is_hot_card = 0"),
        ("min_amount", 3000, "fact_transaction.txnamt >= 3000"),
        ("max_amount", 5000, "fact_transaction.txnamt <= 5000"),
        ("err_severity", 1, "dim_error.err_severity = 1"),
    ],
)
def test_bug3_boolean_amount_and_error_filters(generator, key, value, expected):
    intent = Intent(
        category="total_transactions",
        confidence=0.99,
        query_type="aggregate",
        entities={key: value},
    )
    sql = generator.generate(intent, {}).sql
    assert expected in sql


def test_bug4_detail_view_exposes_terminal_risk_score(generator):
    intent = Intent(
        category="transaction_detail",
        confidence=0.99,
        query_type="detail",
        entities={"detail_fields": ["transaction_id", "terminal_risk_score"], "limit": 10},
    )
    sql = generator.generate(intent, {}).sql
    assert "dim_terminal.terminal_risk_score AS terminal_risk_score" in sql


def test_bug5_hour_range_dict_generates_semantic_range(generator):
    intent = Intent(
        category="transaction_detail",
        confidence=0.99,
        query_type="detail",
        entities={
            "detail_fields": ["transaction_id", "hour24"],
            "hour24": {"from": 10, "to": 14},
            "limit": 10,
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "dim_time.hour24 >= 10 AND dim_time.hour24 <= 14" in sql


def test_bug5_date_range_dict_generates_date_range(generator):
    intent = Intent(
        category="transaction_detail",
        confidence=0.99,
        query_type="detail",
        entities={
            "detail_fields": ["transaction_id", "full_date"],
            "date_range": {"from": "2026-08-15", "to": "2026-08-15"},
            "limit": 10,
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "dim_date.full_date >= '2026-08-15' AND dim_date.full_date <= '2026-08-15'" in sql


def test_bug6_list_filter_generates_in_for_aggregate_and_detail(generator):
    aggregate = Intent(
        category="total_transactions",
        confidence=0.99,
        query_type="aggregate",
        entities={"server_type": ["Primary", "Backup"]},
    )
    detail = Intent(
        category="transaction_detail",
        confidence=0.99,
        query_type="detail",
        entities={
            "server_type": ("Primary", "Backup"),
            "detail_fields": ["transaction_id", "server_type"],
            "limit": 10,
        },
    )
    assert "dim_server.server_type IN ('Primary', 'Backup')" in generator.generate(aggregate, {}).sql
    assert "dim_server.server_type IN ('Primary', 'Backup')" in generator.generate(detail, {}).sql


def test_bug7_reference_date_controls_relative_time_range(generator):
    intent = Intent(
        category="total_transactions",
        confidence=0.99,
        query_type="aggregate",
        entities={"time_range": "last_3_days"},
    )
    sql = generator.generate(intent, {}, reference_date="2026-08-16").sql
    assert "fact_transaction.date_in_sk >= 20260814" in sql
    assert "fact_transaction.date_in_sk < 20260817" in sql


def test_bug7_context_reference_date_is_supported_without_breaking_signature(generator):
    intent = Intent(
        category="total_transactions",
        confidence=0.99,
        query_type="aggregate",
        entities={"time_range": "today"},
    )
    sql = generator.generate(intent, {"reference_date": "2026-08-16"}).sql
    assert "fact_transaction.date_in_sk >= 20260816" in sql
    assert "fact_transaction.date_in_sk < 20260817" in sql


def test_bug5_invalid_hour_range_fails_closed(generator):
    intent = Intent(
        category="total_transactions",
        confidence=0.99,
        query_type="aggregate",
        entities={"hour24": {"from": 10, "to": 30}},
    )
    with pytest.raises(ValueError, match="range upper bound out of range"):
        generator.generate(intent, {})


def test_is_weekend_filter_generates_boolean_dimension_filter(generator):
    intent = Intent(
        category="total_transactions", confidence=0.99, query_type="aggregate",
        entities={"is_weekend": True},
    )
    sql = generator.generate(intent, {}).sql
    assert "INNER JOIN dim_date" in sql
    assert "dim_date.is_weekend = 1" in sql


def test_is_holiday_filter_generates_boolean_dimension_filter(generator):
    intent = Intent(
        category="total_transactions", confidence=0.99, query_type="aggregate",
        entities={"is_holiday": False},
    )
    sql = generator.generate(intent, {}).sql
    assert "INNER JOIN dim_date" in sql
    assert "dim_date.is_holiday = 0" in sql


def test_enum_string_filters_normalize_case_without_lower_function(generator):
    lifecycle = Intent(
        category="total_transactions", confidence=0.99, query_type="aggregate",
        entities={"lifecycle_stage": "completed"},
    )
    terminal = Intent(
        category="total_transactions", confidence=0.99, query_type="aggregate",
        entities={"entry_mode_desc": "chip"},
    )
    lifecycle_sql = generator.generate(lifecycle, {}).sql
    terminal_sql = generator.generate(terminal, {}).sql
    assert "dim_status.lifecycle_stage = 'Completed'" in lifecycle_sql
    assert "dim_status.lifecycle_stage = 'completed'" not in lifecycle_sql
    assert "dim_terminal.entry_mode_desc = 'Chip'" in terminal_sql
    assert "dim_terminal.entry_mode_desc = 'chip'" not in terminal_sql


def test_detail_is_hot_card_is_allowlisted(generator):
    intent = Intent(
        category="transaction_detail", confidence=0.99, query_type="detail",
        entities={"detail_fields": ["transaction_id", "is_hot_card"], "limit": 5},
    )
    sql = generator.generate(intent, {}).sql
    assert "fact_transaction.is_hot_card AS is_hot_card" in sql


def test_detail_joins_only_required_projection_and_filters(generator):
    intent = Intent(
        category="transaction_detail", confidence=0.99, query_type="detail",
        entities={
            "detail_fields": ["transaction_id", "transaction_amount", "server_name"],
            "server_name": "SRV-A",
            "limit": 5,
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "JOIN dim_server" in sql
    assert "dim_terminal" not in sql
    assert "dim_status" not in sql
    assert "dim_error" not in sql
    assert "dim_time" not in sql
    assert "dim_date" not in sql


def test_detail_filter_still_adds_join_for_unselected_dimension(generator):
    intent = Intent(
        category="transaction_detail", confidence=0.99, query_type="detail",
        entities={
            "detail_fields": ["transaction_id", "transaction_amount"],
            "device_category": "ATM",
            "limit": 5,
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "LEFT JOIN dim_terminal" in sql
    assert "dim_terminal.device_category = 'ATM'" in sql


def test_detail_time_of_day_adds_only_time_join(generator):
    intent = Intent(
        category="transaction_detail", confidence=0.99, query_type="detail",
        entities={
            "detail_fields": ["transaction_id", "transaction_amount"],
            "time_of_day": "morning",
            "limit": 5,
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "INNER JOIN dim_time" in sql
    assert "dim_time.hour24 >= 5 AND dim_time.hour24 <= 11" in sql
    assert "dim_date" not in sql
