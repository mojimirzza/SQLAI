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


def test_top_n_detail_generates_individual_rows_not_aggregate(generator):
    intent = Intent(
        category="transaction_detail",
        confidence=0.98,
        query_type="top_n_detail",
        entities={
            "detail_view": "transaction",
            "detail_fields": ["transaction_id", "transaction_amount", "server_name", "terminal_sk", "hour24", "full_date"],
            "time_range": "last_3_days",
            "order_by": {"field": "transaction_amount", "direction": "DESC"},
            "limit": 15,
        },
    )
    generated = generator.generate(intent, {})
    sql = generated.sql.upper()
    assert "SUM(" not in sql
    assert "AVG(" not in sql
    assert "COUNT(" not in sql
    assert "GROUP BY" not in sql
    assert "FACT_TRANSACTION.TXNAMT AS TRANSACTION_AMOUNT" in sql
    assert "DIM_SERVER.SERVER_NAME AS SERVER_NAME" in sql
    assert "FACT_TRANSACTION.TERMINAL_SK AS TERMINAL_SK" in sql
    assert "DIM_TIME.HOUR24 AS HOUR24" in sql
    assert "DIM_DATE.FULL_DATE AS FULL_DATE" in sql
    assert "ORDER BY FACT_TRANSACTION.TXNAMT DESC" in sql
    assert "LIMIT 15" in sql
    assert "DATE_IN_SK >=" in sql


def test_detail_requires_bounded_limit(generator):
    intent = Intent(
        category="transaction_detail",
        confidence=0.95,
        query_type="detail",
        entities={"detail_fields": ["transaction_id"]},
    )
    with pytest.raises(ValueError, match="requires an explicit positive limit"):
        generator.generate(intent, {})


def test_detail_rejects_arbitrary_field(generator):
    intent = Intent(
        category="transaction_detail",
        confidence=0.95,
        query_type="detail",
        entities={"detail_fields": ["customer_name"], "limit": 10},
    )
    with pytest.raises(ValueError, match="Unsupported detail field"):
        generator.generate(intent, {})


def test_top_n_detail_rejects_arbitrary_order_expression(generator):
    intent = Intent(
        category="transaction_detail",
        confidence=0.95,
        query_type="top_n_detail",
        entities={
            "detail_fields": ["transaction_id", "transaction_amount"],
            "order_by": "SUM(txnamt) DESC",
            "limit": 10,
        },
    )
    with pytest.raises(ValueError, match="Unsupported detail order_by value"):
        generator.generate(intent, {})


def test_top_n_aggregate_preserves_existing_aggregate_contract(generator):
    intent = Intent(
        category="total_amount",
        confidence=0.95,
        query_type="top_n_aggregate",
        entities={
            "dimensions": ["server_name"],
            "order_by": "total_amount DESC",
            "limit": 15,
        },
    )
    sql = generator.generate(intent, {}).sql.upper()
    assert "SUM(TXNAMT) AS TOTAL_AMOUNT" in sql
    assert "GROUP BY DIM_SERVER.SERVER_NAME" in sql
    assert "ORDER BY TOTAL_AMOUNT DESC" in sql
    assert "LIMIT 15" in sql


def test_detail_status_and_error_filters_have_approved_joins(generator):
    intent = Intent(
        category="transaction_detail",
        confidence=0.95,
        query_type="top_n_detail",
        entities={
            "detail_fields": ["transaction_id", "transaction_amount", "status_code", "error_description"],
            "status_code": 200,
            "order_by": {"field": "transaction_amount", "direction": "DESC"},
            "limit": 10,
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "INNER JOIN dim_status" in sql
    assert "LEFT JOIN dim_error" in sql
    assert "dim_status.status_code = 200" in sql


def test_detail_limit_is_clamped_to_semantic_view_max(generator):
    intent = Intent(
        category="transaction_detail",
        confidence=0.95,
        query_type="top_n_detail",
        entities={
            "detail_fields": ["transaction_id", "transaction_amount"],
            "order_by": {"field": "transaction_amount", "direction": "DESC"},
            "limit": 9999,
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "LIMIT 100" in sql


def test_reviewer_can_revise_query_shape():
    from core.sql_reviewer import SQLReviewer
    from core.models import Intent, SQLReviewResult
    original = Intent("total_amount", 0.9, {"dimensions": ["server_name"]}, query_type="aggregate")
    review = SQLReviewResult(
        approved=False,
        severity="high",
        issues=["Question requests individual rows"],
        rationale="The result shape is wrong",
        suggested_category="transaction_detail",
        suggested_query_type="top_n_detail",
        suggested_entities={
            "detail_fields": ["transaction_id", "transaction_amount"],
            "order_by": {"field": "transaction_amount", "direction": "DESC"},
            "limit": 15,
        },
    )
    revised = SQLReviewer.revised_intent(original, review)
    assert revised.category == "transaction_detail"
    assert revised.query_type == "top_n_detail"
    assert revised.entities["limit"] == 15


def test_aggregate_string_list_filter_generates_in_clause(generator):
    intent = Intent(
        category="total_transactions",
        confidence=0.99,
        query_type="aggregate",
        entities={
            "server_type": ["Primary", "Backup"],
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "dim_server.server_type IN ('Primary', 'Backup')" in sql
    assert "dim_server.server_type = '['" not in sql


def test_detail_string_list_filter_generates_in_clause(generator):
    intent = Intent(
        category="transaction_detail",
        confidence=0.99,
        query_type="top_n_detail",
        entities={
            "server_type": ("Primary", "Backup"),
            "detail_fields": ["transaction_id", "transaction_amount", "server_type"],
            "order_by": {"field": "transaction_amount", "direction": "DESC"},
            "limit": 15,
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "dim_server.server_type IN ('Primary', 'Backup')" in sql
    assert "dim_server.server_type = '['" not in sql


def test_numeric_list_filter_generates_unquoted_in_clause(generator):
    intent = Intent(
        category="total_transactions",
        confidence=0.99,
        query_type="aggregate",
        entities={
            "status_code": [200, 201],
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "dim_status.status_code IN (200, 201)" in sql


def test_scalar_string_filter_remains_equality(generator):
    intent = Intent(
        category="total_transactions",
        confidence=0.99,
        query_type="aggregate",
        entities={
            "server_type": "Primary",
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "dim_server.server_type = 'Primary'" in sql


def test_string_list_filter_escapes_sql_quotes(generator):
    intent = Intent(
        category="total_transactions",
        confidence=0.99,
        query_type="aggregate",
        entities={
            "server_type": ["Primary's", "Backup"],
        },
    )
    sql = generator.generate(intent, {}).sql
    assert "dim_server.server_type IN ('Primary''s', 'Backup')" in sql
