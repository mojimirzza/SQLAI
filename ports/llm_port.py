from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class StructuredOutput:
    intent: str
    confidence: float
    entities: dict[str, Any] = field(default_factory=dict)
    needs_clarification: bool = False
    clarification_question: str | None = None
    answer: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    query_type: str = "aggregate"
    needs_business_context: bool = False
    relevant_tables: list[str] = field(default_factory=list)


class LLMPort(Protocol):
    def generate(self, prompt: str, system_prompt: str | None = None, schema: dict | None = None) -> StructuredOutput: ...
