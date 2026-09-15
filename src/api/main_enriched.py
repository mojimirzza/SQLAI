"""
Ultimate Text-to-SQL v2.2 — Enriched Edition (Memory + Baseline)
-----------------------------------------------------------------
Combines Zero-Mem historical context with Baseline Enrichment.
"""
import uuid
from typing import Optional
from fastapi import FastAPI, Header
from pydantic import BaseModel

from core.models import UserQuery
from core.orchestrator import Orchestrator
from core.enriched_orchestrator import EnrichedOrchestrator
from core.intent_extractor import IntentExtractor
from core.memory_intent_extractor import MemoryAwareIntentExtractor
from core.context_builder import ContextBuilder
from core.sql_generator import SQLGenerator
from core.sql_reviewer import SQLReviewer
from core.dual_synthesizer import DualSynthesizer
from core.baseline_enricher import BaselineEnricher
from adapters.openai_adapter import OpenAIAdapter
from adapters.inmemory_vector_adapter import InMemoryVectorAdapter
from adapters.sqlglot_validator import SQLGlotValidator
from adapters.duckdb_executor import DuckDBExecutor
from adapters.yaml_semantic_adapter import YAMLSemanticAdapter
from adapters.json_logger_adapter import JSONLoggerAdapter
from adapters.sqlite_memory_adapter import SQLiteMemoryAdapter
from config.settings import settings
from core.policy_gate import PolicyGate

app = FastAPI(title="Ultimate Text-to-SQL v2.2 — Enriched (Memory + Baseline)")

# --- Core adapters ---
llm = OpenAIAdapter(settings.llm_api_key, settings.llm_model, settings.llm_base_url)
vector = InMemoryVectorAdapter(settings.TABLE_DESCRIPTIONS_PATH)
semantic = YAMLSemanticAdapter(settings.SEMANTIC_LAYER_PATH)
logger = JSONLoggerAdapter()

# --- Memory layer (Zero-Mem) ---
memory_store = SQLiteMemoryAdapter("data/memory.db")

# --- Shared database executor ---
db_executor = DuckDBExecutor(settings.DUCKDB_PATH)

# --- Baseline enricher (shares executor) ---
baseline_enricher = BaselineEnricher(db_executor)

# --- Base components ---
base_intent_extractor = IntentExtractor(
    llm,
    mschema_path=settings.MSCHEMA_PATH,
    semantic_layer_path=settings.SEMANTIC_LAYER_PATH,
)
base_orchestrator = Orchestrator(
    base_intent_extractor,
    ContextBuilder(vector, settings.TABLE_DESCRIPTIONS_PATH, settings.MSCHEMA_PATH),
    SQLGenerator(semantic),
    SQLGlotValidator(),
    db_executor,
    DualSynthesizer(llm),
    logger,
    settings.POLICY_PATH,
    sql_reviewer=SQLReviewer(llm)
)

# --- Wrap intent extractor with memory ---
memory_intent_extractor = MemoryAwareIntentExtractor(base_intent_extractor, memory_store)
base_orchestrator.intent_extractor = memory_intent_extractor

# --- Final enriched orchestrator (memory + baseline) ---
policy_gate = PolicyGate(base_orchestrator.policies)
orchestrator = EnrichedOrchestrator(base_orchestrator, memory_store, baseline_enricher, policy_gate=policy_gate)


class QueryReq(BaseModel):
    text: str
    user_id: str = "user_001"
    user_role: str = "analyst"


@app.post("/query")
async def handle_query(req: QueryReq, session_id: Optional[str] = Header(None), x_user_id: Optional[str] = Header(None), x_user_role: Optional[str] = Header(None)):
    trusted_user_id = x_user_id or req.user_id
    trusted_role = x_user_role or req.user_role
    q = UserQuery(req.text, trusted_user_id, trusted_role, session_id or str(uuid.uuid4()))
    return orchestrator.process(q)


@app.get("/health")
def health():
    return {"status": "ok", "version": "v2.2-enriched", "features": ["zero-mem", "baseline-enrichment"]}


@app.get("/memory/{user_id}")
async def get_user_memory(user_id: str, x_user_id: Optional[str] = Header(None), x_user_role: Optional[str] = Header(None)):
    decision = policy_gate.authorize_memory(x_user_id or "", user_id, x_user_role or "")
    if not decision.allowed:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail=decision.reason)
    """Debug: view memory context for a user."""
    ctx = memory_store.build_memory_context(user_id, "", "")
    return {
        "frequent_categories": ctx.frequent_categories,
        "frequent_entities": ctx.frequent_entities,
        "user_preferences": ctx.user_preferences,
        "recent_queries_count": len(ctx.recent_queries),
        "same_session_queries_count": len(ctx.same_session_queries),
        "referenced_time_ranges": ctx.referenced_time_ranges,
        "referenced_servers": ctx.referenced_servers,
        "referenced_device_categories": ctx.referenced_device_categories,
        "referenced_status_codes": ctx.referenced_status_codes,
    }
