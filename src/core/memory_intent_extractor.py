"""
Memory-Aware Intent Extractor — Star Schema Edition
----------------------------------------------------
Wraps the base IntentExtractor to inject MemoryContext into the LLM prompt.
Memory is fetched and built WITHOUT LLM (<50ms).
LLM only consumes the context for better intent extraction.
"""
from core.models import UserQuery, Intent
from core.intent_extractor import INTENT_SCHEMA
from ports.llm_port import LLMPort
from ports.memory_store_port import MemoryStorePort, MemoryContext


MEMORY_AWARE_INTENT_SYSTEM_PROMPT = """You are the intent/planning layer of a transaction monitoring Text-to-SQL system.
Your job is NOT to write SQL. Return only structured intent data.

Supported metrics (categories):
- total_transactions: COUNT(*) of transactions
- total_amount: SUM(txnamt) total monetary amount
- approval_rate: SUM(is_approved)*100.0/COUNT(*) approval percentage
- avg_switch_latency: AVG(switch_latency_ms) average latency
- stuck_transactions: SUM(is_stuck) count of stuck transactions
- hot_card_count: SUM(is_hot_card) count of hot card transactions
- error_count: SUM(has_error) count of transactions with errors

Supported dimensions:
- Time: year, quarter, month, month_name, day_of_month, day_of_week, day_name, week_of_year, is_weekend, is_holiday, hour24, hour12, am_pm, time_of_day
- Server: server_name, server_type, location
- Terminal: device_category, entry_mode_desc, terminal_risk_score
- Status: status_code, lifecycle_stage
- Error: err_severity, error_description

Supported query types:
- aggregate
- detail
- top_n_detail
- top_n_aggregate

Extract:
- category: the closest supported metric for aggregate queries, or transaction_detail for detail queries
- query_type: one of aggregate, detail, top_n_detail, top_n_aggregate
- confidence: 0..1
- entities: dimensions, time_range, start_date, end_date, server_name, server_type,
  location, device_category, entry_mode_desc, status_code, lifecycle_stage,
  err_severity, error_description, time_of_day, hour24, order_by, limit
- needs_business_context: true only when business definitions needed
- relevant_tables: only from {{fact_transaction, dim_date, dim_time, dim_server, dim_terminal, dim_status, dim_error}}
- needs_clarification: true when materially ambiguous

Rules:
1. Never invent tables, columns, metrics, dates, or business definitions.
2. Preserve aggregation and dimensions requested by user.
3. DETAIL means individual fact rows; TOP_N_DETAIL means individual rows ordered by an approved detail field; TOP_N_AGGREGATE means grouped results ordered by an aggregate metric.
4. For detail queries, use only these semantic detail fields: transaction_id, trace, refnum, msgno, transaction_amount, server_name, server_type, terminal_sk, device_category, hour24, status_code, lifecycle_stage, err_severity, error_description, full_date.
5. Do not put SQL or raw SQL expressions into entities.
6. Normalize relative dates to time_range labels (today, yesterday, this_week, this_month, last_month, last_3_months, etc.).
7. If confidence < 0.70, ask one concise clarification question.
8. Date SKs are INTEGER YYYYMMDD. Time SKs are INTEGER seconds-since-midnight (0-86399).

MEMORY CONTEXT (use to resolve pronouns, implicit references, and preferences):
User typically asks about: {frequent_categories}
Recent filter patterns: {frequent_entities}
User preferences: {user_preferences}
Recent time ranges: {referenced_time_ranges}
Recent servers: {referenced_servers}
Recent device categories: {referenced_device_categories}
Recent status codes: {referenced_status_codes}
Last similar query category: {last_similar_category}
Last similar query entities: {last_similar_entities}
Session history (last 5): {session_history}

If user says "حالا همون", "بعدی", "قبلی", "همون", "مثل قبل", "also", "now", "again":
refer to session history and last similar query to resolve references.
If user specifies unit (million, billion) without repeating each time, apply preference.
"""


class MemoryAwareIntentExtractor:
    """
    Wraps IntentExtractor with memory injection.
    Memory built WITHOUT LLM (<50ms).
    LLM only receives context to improve extraction.
    """

    def __init__(self, base_extractor, memory_store: MemoryStorePort):
        self.base_extractor = base_extractor
        self.memory_store = memory_store
        self.llm = base_extractor.llm
        self.confidence_threshold = base_extractor.confidence_threshold

    def extract(self, query: UserQuery) -> Intent:
        # Step 1: Build memory context deterministically (<50ms, no LLM)
        memory = self.memory_store.build_memory_context(
            user_id=query.user_id,
            session_id=query.session_id,
            current_query_text=query.text
        )

        # Step 2: Build enriched prompt with memory
        system = MEMORY_AWARE_INTENT_SYSTEM_PROMPT.format(
            frequent_categories=", ".join(memory.frequent_categories) or "none",
            frequent_entities=str(memory.frequent_entities) or "none",
            user_preferences=str(memory.user_preferences) or "none",
            referenced_time_ranges=", ".join(memory.referenced_time_ranges) or "none",
            referenced_servers=", ".join(memory.referenced_servers) or "none",
            referenced_device_categories=", ".join(memory.referenced_device_categories) or "none",
            referenced_status_codes=", ".join(memory.referenced_status_codes) or "none",
            last_similar_category=memory.last_similar_category or "none",
            last_similar_entities=str(memory.last_similar_entities) or "none",
            session_history=" | ".join(
                f"Q{i+1}: {r.query_text}"
                for i, r in enumerate(reversed(memory.same_session_queries))
            ) or "none",
        )

        prompt = f"User query: {query.text}\nUser role: {query.user_role}"
        if getattr(self.base_extractor, "semantic_context", ""):
            prompt += f"\n\n{self.base_extractor.semantic_context}"
        if getattr(self.base_extractor, "mschema_context", ""):
            prompt += f"\n\n{self.base_extractor.mschema_context}"

        # Step 3: Call LLM with memory-aware system prompt + schema
        result = self.llm.generate(prompt, system, schema=INTENT_SCHEMA)

        needs = result.needs_clarification or result.confidence < self.confidence_threshold

        # Step 4: Post-process with memory (deterministic, no LLM)
        entities = result.entities or {}

        # Auto-fill implicit server from history
        if not entities.get("server_name") and memory.frequent_entities.get("server_name"):
            if any(w in query.text.lower() for w in ["سرور", "server", "سوییچ", "switch"]):
                entities["server_name"] = memory.frequent_entities["server_name"][0]

        # Auto-fill implicit device_category from history
        if not entities.get("device_category") and memory.frequent_entities.get("device_category"):
            if any(w in query.text.lower() for w in ["دستگاه", "ترمینال", "device", "terminal"]):
                entities["device_category"] = memory.frequent_entities["device_category"][0]

        # Auto-fill implicit time range from history
        if not entities.get("time_range") and memory.referenced_time_ranges:
            if any(w in query.text.lower() for w in [
                "ماه", "هفته", "سال", "month", "week", "year",
                "امروز", "دیروز", "today", "yesterday"
            ]):
                entities["time_range"] = memory.referenced_time_ranges[0]

        # Auto-fill implicit dimensions from last similar query
        if not entities.get("dimensions") and memory.last_similar_entities.get("dimensions"):
            if any(w in query.text.lower() for w in ["همون", "مثل", "like", "same", "also"]):
                entities["dimensions"] = memory.last_similar_entities["dimensions"]

        # Apply user preference for unit
        if memory.user_preferences.get("unit"):
            entities["preferred_unit"] = memory.user_preferences["unit"]

        return Intent(
            category=result.intent,
            confidence=max(0.0, min(1.0, result.confidence)),
            entities=entities,
            needs_clarification=needs,
            clarification_question=result.clarification_question,
            needs_business_context=bool(result.needs_business_context),
            relevant_tables=list(result.relevant_tables or []),
            query_type=getattr(result, "query_type", None) or (getattr(result, "data", {}) or {}).get("query_type") or (entities or {}).get("query_type", "aggregate"),
        )
