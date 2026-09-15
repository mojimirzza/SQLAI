from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from core.policy_gate import PolicyGate
from core.sql_generator import SQLGenerator
from core.models import Intent


def test_policy_gate_role_and_memory_access():
    gate = PolicyGate({"role_rules": {"query": ["analyst"], "memory_admin": ["admin"]}})
    assert gate.authorize_query("analyst").allowed
    assert not gate.authorize_query("guest").allowed
    assert gate.authorize_memory("u1", "u1", "analyst").allowed
    assert gate.authorize_memory("u1", "u2", "admin").allowed
    assert not gate.authorize_memory("u1", "u2", "analyst").allowed


def test_sql_generator_rejects_unknown_dimension():
    class Semantic:
        def get_metric(self, name):
            return type("M", (), {"name": name, "sql_expression": "COUNT(*)", "table": "fact_transaction", "dimensions": [], "joins": [], "filters": []})()
    gen = SQLGenerator(Semantic())
    try:
        gen.generate(Intent("total_transactions", 1.0, {"dimensions": ["not_a_dimension"]}), {})
    except ValueError as exc:
        assert "Unsupported dimension" in str(exc)
    else:
        raise AssertionError("unsupported dimensions must fail explicitly")


def test_explicit_end_date_is_inclusive():
    start, end = SQLGenerator._date_sk_bounds(None, "2026-08-01", "2026-08-03")
    assert start == 20260801
    assert end == 20260804


def test_relative_date_contract():
    start, end = SQLGenerator._date_sk_bounds("last_3_months", None, None)
    assert start is not None and end is not None and start < end
