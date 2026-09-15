"""
Follow-up Suggester Agent — Mode: suggest
Generates 2-3 natural follow-up questions after a successful query.
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from typing import Any

from core.db_reader import DBReader
from core.llm_client import LLMClient
from core.state_manager import StateManager


class FollowupSuggester:
    """Agent that suggests follow-up questions based on query result + history."""

    def __init__(self, db: DBReader, llm: LLMClient, state: StateManager,
                 max_suggestions: int = 3):
        self.db = db
        self.llm = llm
        self.state = state
        self.max_suggestions = max_suggestions

    def run(self, query_id: str) -> list[str]:
        """Generate follow-up suggestions for a specific query."""
        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()

        # 1. Fetch query record
        record = self.db.get_query_by_id(query_id)
        if not record:
            return []

        # 2. Fetch session history for context
        session_queries = self.db.get_session_queries(
            record.get("session_id", ""), limit=5
        )

        # 3. Fetch semantic layer for available metrics/dims
        metrics = self.db.list_metrics()
        dimensions = self.db.list_dimensions()

        # 4. Generate suggestions
        suggestions = self._generate_suggestions(record, session_queries, metrics, dimensions)

        # 5. Save state
        self.state.save_suggestions(
            suggestion_id=run_id,
            query_id=query_id,
            session_id=record.get("session_id", ""),
            suggestions=suggestions,
        )
        self.state.log_run(
            run_id=run_id, agent_name="FollowupSuggester", mode="suggest",
            started_at=started_at, finished_at=datetime.now(),
            success=True, output_summary=f"{len(suggestions)} suggestions for {query_id}",
        )

        return suggestions

    def _generate_suggestions(self, record: dict, session_queries: list[dict],
                              metrics: list[str], dimensions: list[str]) -> list[str]:
        with open("prompts/suggester_system.md", encoding="utf-8") as f:
            system = f.read()

        session_context = []
        for sq in session_queries[:5]:
            session_context.append(
                f"- {sq.get('query_text', '')} ({sq.get('intent_category', 'unknown')})"
            )

        prompt = f"""Original query: {record.get('query_text', '')}
Intent category: {record.get('intent_category', 'unknown')}
Metric used: {record.get('sql_metric', 'unknown')}
Dimensions: {record.get('sql_dimensions', '[]')}
Result rows: {record.get('execution_row_count', 0)}

Session history:
{chr(10).join(session_context)}

Available metrics: {', '.join(metrics)}
Available dimensions: {', '.join(dimensions)}

Generate {self.max_suggestions} concise follow-up questions the user might want to ask next.
Write in the same language as the original query (Persian or English).
Each suggestion must be answerable by the existing semantic layer.

Return JSON: {{"suggestions": ["...", "..."]}}
"""

        schema = {
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": self.max_suggestions,
                },
            },
            "required": ["suggestions"],
        }

        result = self.llm.generate(prompt, system=system, schema=schema)
        return result.get("suggestions", [])
