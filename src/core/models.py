from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RequestType(Enum):
    SQL_ONLY = "sql_only"
    SQL_WITH_RAG = "sql_with_rag"
    CLARIFICATION = "clarification"
    REJECTED = "rejected"


class Persona(Enum):
    BUSINESS_ANALYST = "ba"
    CEO = "ceo"


@dataclass
class UserQuery:
    text: str
    user_id: str
    user_role: str
    session_id: str


@dataclass
class Intent:
    category: str
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    needs_clarification: bool = False
    clarification_question: str | None = None
    needs_business_context: bool = False
    relevant_tables: list[str] = field(default_factory=list)
    query_type: str = "aggregate"


@dataclass
class JoinSpec:
    """A single JOIN clause specification."""
    table: str
    on: str
    type: str  # INNER or LEFT


@dataclass
class GeneratedSQL:
    sql: str
    metric_used: str | None
    dimensions: list[str]
    filters: list[str]
    joins: list[JoinSpec] = field(default_factory=list)


class SQLReviewResult(BaseModel):
    """Structured semantic review. The reviewer never returns executable SQL."""

    approved: bool
    severity: str = Field(default="none", pattern="^(none|low|medium|high)$")
    issues: list[str] = Field(default_factory=list)
    rationale: str = ""
    suggested_category: str | None = None
    suggested_query_type: str | None = Field(default=None, pattern="^(aggregate|detail|top_n_detail|top_n_aggregate)$")
    suggested_entities: dict[str, Any] = Field(default_factory=dict)


@dataclass
class DualResponse:
    request_type: RequestType
    sql: str | None
    ba_answer: str | None
    ceo_answer: str | None
    explanation: str | None
    confidence: float
    trace_id: str
    suggested_followups: list[str] = field(default_factory=list)
