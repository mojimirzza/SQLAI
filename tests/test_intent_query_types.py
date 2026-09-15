from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from core.models import UserQuery
from core.intent_extractor import IntentExtractor
from core.memory_intent_extractor import MemoryAwareIntentExtractor
from ports.llm_port import StructuredOutput


class FakeLLM:
    def __init__(self):
        self.last_schema = None

    def generate(self, prompt, system_prompt=None, schema=None):
        self.last_schema = schema
        return StructuredOutput(
            intent="transaction_detail",
            confidence=0.97,
            entities={
                "detail_view": "transaction",
                "detail_fields": ["transaction_id", "transaction_amount", "server_name"],
                "order_by": {"field": "transaction_amount", "direction": "DESC"},
                "limit": 15,
            },
            data={"query_type": "top_n_detail"},
            query_type="top_n_detail",
            needs_business_context=False,
            relevant_tables=[],
        )


def _query():
    return UserQuery("Show me the top 15 highest-value transactions", "u1", "analyst", "s1")


def test_intent_extractor_preserves_query_type():
    llm = FakeLLM()
    intent = IntentExtractor(llm).extract(_query())
    assert intent.query_type == "top_n_detail"
    assert llm.last_schema["properties"]["query_type"]["enum"] == ["aggregate", "detail", "top_n_detail", "top_n_aggregate"]


class FakeMemory:
    def build_memory_context(self, **kwargs):
        class C:
            frequent_categories=[]
            frequent_entities={}
            user_preferences={}
            referenced_time_ranges=[]
            referenced_servers=[]
            referenced_device_categories=[]
            referenced_status_codes=[]
            last_similar_category=None
            last_similar_entities={}
            same_session_queries=[]
        return C()


def test_memory_intent_extractor_preserves_query_type():
    base = IntentExtractor(FakeLLM())
    intent = MemoryAwareIntentExtractor(base, FakeMemory()).extract(_query())
    assert intent.query_type == "top_n_detail"
