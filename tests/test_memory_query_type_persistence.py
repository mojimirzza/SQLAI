from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ports.memory_store_port import QueryRecord
from src.adapters.sqlite_memory_adapter import SQLiteMemoryAdapter


def test_query_type_persists_and_legacy_schema_migrates(tmp_path):
    db = tmp_path / "memory.db"
    memory = SQLiteMemoryAdapter(str(db))
    record = QueryRecord(
        id="q1",
        user_id="u1",
        session_id="s1",
        query_text="top transactions",
        timestamp=datetime.now(timezone.utc),
        intent_category="transaction_detail",
        intent_query_type="top_n_detail",
        generated_sql="SELECT ... LIMIT 15",
    )
    memory.save(record)
    history = memory.get_session_history("s1")
    assert history[0].intent_query_type == "top_n_detail"
