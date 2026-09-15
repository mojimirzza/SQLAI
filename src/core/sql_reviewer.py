import json
from copy import deepcopy

from core.models import GeneratedSQL, Intent, SQLReviewResult
from ports.llm_port import LLMPort
from ports.sql_reviewer_port import SQLReviewerPort


SQL_REVIEW_SYSTEM_PROMPT = """You are the semantic reviewer for a transaction monitoring Text-to-SQL system.

You do NOT write SQL. You review the proposed SQL and return structured feedback only.
Your job is to catch semantic mistakes that syntax validation cannot catch.

Check:
1. Does the SQL answer the user's actual question?
2. Is the selected metric appropriate? (total_transactions, total_amount, approval_rate, avg_switch_latency, stuck_transactions, hot_card_count, error_count)
3. Are requested dimensions/detail fields used correctly? (dim_date, dim_time, dim_server, dim_terminal, dim_status, dim_error)
4. Are JOIN types correct? Required dimensions (dim_date, dim_time, dim_server, dim_status) must use INNER JOIN. Optional dimensions (dim_terminal, dim_error) must use LEFT JOIN.
5. Are filters and time ranges faithful to the request? Date filters must use YYYYMMDD integer SKs, not DATE strings. Time filters must use seconds-since-midnight integer SKs.
6. Is aggregation correct for aggregate queries? For DETAIL/TOP_N_DETAIL, the query must return individual fact rows and must not introduce SUM/AVG/COUNT aggregation or GROUP BY.
7. For TOP_N_DETAIL, is ORDER BY a semantic-layer-approved detail field, with a bounded LIMIT?
8. Does TOP_N_AGGREGATE retain the requested grouping and aggregate metric?
9. Is the selected category/metric/query type supported by the supplied semantic context?
10. Is there an unnecessary or missing grouping/filter implied by the question?
11. Are duplicate JOINs avoided? Each dimension table should appear at most once.

Important:
- Never invent tables, columns, metrics, or business definitions.
- Never return SQL.
- If a correction is needed, express it as suggested_category, suggested_query_type, and/or suggested_entities.
- Only set approved=true when the proposed SQL is semantically aligned with the question.
- Prefer a safe rejection over a guess.
- Date SKs are INTEGER YYYYMMDD. Time SKs are INTEGER 0-86399.
"""


class SQLReviewer(SQLReviewerPort):
    """LLM-backed semantic gate. It critiques SQL but never authors executable SQL."""

    REVIEW_SCHEMA = {
        "type": "object",
        "properties": {
            "approved": {"type": "boolean"},
            "severity": {"type": "string", "enum": ["none", "low", "medium", "high"]},
            "issues": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
            "suggested_category": {"type": ["string", "null"]},
            "suggested_query_type": {"type": ["string", "null"], "enum": ["aggregate", "detail", "top_n_detail", "top_n_aggregate", None]},
            "suggested_entities": {"type": "object"},
        },
        "required": ["approved", "severity", "issues", "rationale", "suggested_category", "suggested_query_type", "suggested_entities"],
        "additionalProperties": False,
    }

    def __init__(self, llm: LLMPort):
        self.llm = llm

    def review(self, user_query: str, intent: Intent, generated: GeneratedSQL, context: dict) -> SQLReviewResult:
        prompt = {
            "user_query": user_query,
            "intent": {
                "category": intent.category,
                "query_type": intent.query_type,
                "confidence": intent.confidence,
                "entities": intent.entities,
                "relevant_tables": intent.relevant_tables,
            },
            "generated_sql": generated.sql,
            "metric_used": generated.metric_used,
            "dimensions": generated.dimensions,
            "filters": generated.filters,
            "joins": [{"table": j.table, "type": j.type, "on": j.on} for j in generated.joins],
            "context": context,
        }
        result = self.llm.generate(
            json.dumps(prompt, ensure_ascii=False, default=str),
            SQL_REVIEW_SYSTEM_PROMPT,
            schema=self.REVIEW_SCHEMA,
        )
        data = getattr(result, "data", None) or {}
        return SQLReviewResult.model_validate(data)

    @staticmethod
    def should_review(intent: Intent, generated: GeneratedSQL, context: dict) -> bool:
        """Avoid an extra LLM call for very simple, low-risk requests."""
        score = 0
        if len(generated.dimensions) > 1:
            score += 1
        if generated.filters:
            score += 1
        if generated.joins:
            score += 1  # JOINs add semantic risk
        entities = intent.entities or {}
        if entities.get("time_range") or entities.get("start_date") or entities.get("end_date"):
            score += 1
        if entities.get("order_by") or entities.get("limit"):
            score += 1
        if context.get("business_context"):
            score += 1
        return score >= 2

    @staticmethod
    def revised_intent(intent: Intent, review: SQLReviewResult) -> Intent:
        updated = deepcopy(intent)
        if review.suggested_category:
            updated.category = review.suggested_category
        if review.suggested_query_type:
            updated.query_type = review.suggested_query_type
        if review.suggested_entities:
            merged = deepcopy(updated.entities)
            merged.update(review.suggested_entities)
            updated.entities = merged
        return updated
