from __future__ import annotations

from typing import Protocol

from core.models import GeneratedSQL, Intent, SQLReviewResult


class SQLReviewerPort(Protocol):
    def review(self, user_query: str, intent: Intent, generated: GeneratedSQL, context: dict) -> SQLReviewResult: ...
