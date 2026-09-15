"""Stable v1 contracts for Situation Memory consumption.

The contract deliberately separates memory (evidence/context) from decision authority.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class SituationMemoryRequest:
    query_id: str | None = None
    investigation_id: str | None = None
    entities: Mapping[str, list[str]] | None = None
    current_situation_id: str | None = None
    limit: int = 5
    min_score: float = 0.60


@dataclass(frozen=True)
class SituationMemoryItem:
    situation_id: str
    score: float
    status: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class SituationMemoryResponse:
    schema_version: str
    request: SituationMemoryRequest
    items: tuple[SituationMemoryItem, ...]
    authority: str = "evidence_only"
    decision_binding: bool = False
