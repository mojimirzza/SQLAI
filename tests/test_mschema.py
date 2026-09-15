from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import yaml

from core.context_builder import ContextBuilder
from core.intent_extractor import IntentExtractor
from core.models import Intent
from scripts.mschema_compiler import compile_mschema


class _Doc:
    def __init__(self, content):
        self.content = content


class _Vector:
    def search(self, category, top_k=3):
        return [_Doc("biz")]


def test_committed_mschema_has_semantic_fks():
    path = Path("src/config/mschema.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "fact_transaction" in data["tables"]
    assert any(
        fk["from_table"] == "fact_transaction" and fk["from_column"] == "server_sk" and fk["to_table"] == "dim_server"
        for fk in data["foreign_keys"]
    )


def test_context_builder_includes_mschema_and_fk(tmp_path):
    base = tmp_path / "tables.yaml"
    base.write_text(Path("docs/table_descriptions.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    ctx = ContextBuilder(_Vector(), str(base), "src/config/mschema.yaml")
    intent = Intent(
        category="avg_switch_latency",
        confidence=0.95,
        entities={},
        needs_clarification=False,
        needs_business_context=False,
        relevant_tables=["fact_transaction", "dim_server"],
    )
    result = ctx.build(intent)
    assert "mschema" in result
    assert "fact_transaction" in result["mschema"]
    assert "server_sk" in result["mschema"]
    assert "Foreign Keys" in result["mschema"]


def test_compiler_sqlite_is_build_time_and_allowlisted(tmp_path):
    db = tmp_path / "fixture.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
    CREATE TABLE dim_server(server_sk INTEGER PRIMARY KEY, server_name TEXT, location TEXT, secret_token TEXT);
    CREATE TABLE fact_transaction(transaction_sk INTEGER PRIMARY KEY, server_sk INTEGER, txnamt DECIMAL(18,2), switch_latency_ms INTEGER,
        FOREIGN KEY(server_sk) REFERENCES dim_server(server_sk));
    INSERT INTO dim_server VALUES (1, 'Tehran-01', 'Tehran', 'DO-NOT-COPY');
    INSERT INTO fact_transaction VALUES (10, 1, 125.5, 847);
    """)
    conn.commit(); conn.close()
    out = tmp_path / "mschema.yaml"
    data = compile_mschema(str(db), str(out), "src/config/semantic_layer.yaml", allow_real_samples=True)
    server_samples = next(c for c in data["tables"]["dim_server"]["columns"] if c["name"] == "server_name")["sample_values"]
    secret_samples = next(c for c in data["tables"]["dim_server"]["columns"] if c["name"] == "secret_token")["sample_values"]
    assert server_samples == ["Tehran-01"]
    assert secret_samples == []
    assert any(fk["from_column"] == "server_sk" for fk in data["foreign_keys"])


def test_intent_extractor_uses_optional_mschema_without_changing_signature(tmp_path):
    class FakeLLM:
        def __init__(self):
            self.seen = None
        def generate(self, prompt, system_prompt, schema=None):
            self.seen = prompt + "\n" + system_prompt
            return type("R", (), {
                "intent": "avg_switch_latency",
                "confidence": 0.95,
                "entities": {},
                "needs_clarification": False,
                "clarification_question": None,
                "needs_business_context": False,
                "relevant_tables": ["fact_transaction", "dim_server"],
            })()
    llm = FakeLLM()
    ext = IntentExtractor(llm, mschema_path="src/config/mschema.yaml")
    from core.models import UserQuery
    ext.extract(UserQuery("latency by server", "u1", "analyst", "s1"))
    assert "fact_transaction" in llm.seen
    assert "server_sk" in llm.seen
    assert "Foreign Keys" in llm.seen
