from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass
class QueryRecord:
    id: str
    user_id: str
    session_id: str
    query_text: str
    timestamp: datetime
    intent_category: str = ""
    intent_query_type: str = "aggregate"
    intent_entities: dict[str, Any] = field(default_factory=dict)
    generated_sql: str = ""
    sql_metric: str | None = None
    sql_dimensions: list[str] = field(default_factory=list)
    sql_filters: list[str] = field(default_factory=list)
    sql_joins: list[dict[str, Any]] = field(default_factory=list)
    execution_row_count: int = 0
    execution_success: bool = False
    response_type: str = ""
    confidence: float = 0.0


@dataclass
class MemoryContext:
    frequent_categories: list[str] = field(default_factory=list)
    frequent_entities: dict[str, list[str]] = field(default_factory=dict)
    user_preferences: dict[str, str] = field(default_factory=dict)
    recent_queries: list[QueryRecord] = field(default_factory=list)
    same_session_queries: list[QueryRecord] = field(default_factory=list)
    last_similar_category: str | None = None
    last_similar_entities: dict[str, Any] = field(default_factory=dict)
    referenced_time_ranges: list[str] = field(default_factory=list)
    referenced_servers: list[str] = field(default_factory=list)
    referenced_device_categories: list[str] = field(default_factory=list)
    referenced_status_codes: list[str] = field(default_factory=list)


class MemoryStorePort(Protocol):
    def get_context(self, user_id: str, session_id: str, current_query_text: str = "") -> MemoryContext: ...
    def get_session_history(self, session_id: str, limit: int = 10) -> list[QueryRecord]: ...
    def save(self, record: QueryRecord) -> None: ...
