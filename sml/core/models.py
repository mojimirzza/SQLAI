from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class Signal:
    signal_id: str
    signal_type: str
    observed_at: datetime
    source_system: str
    source_reference: str
    entities: dict[str, list[str]] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

@dataclass
class CorrelationDecision:
    signal_id: str
    candidate_signal_id: str
    score: float
    rule_version: str
    matched_entities: dict[str, list[str]]
    temporal_distance_seconds: float
    decision: str

@dataclass
class Situation:
    situation_id: str
    status: str
    created_at: datetime
    first_signal_at: datetime
    last_signal_at: datetime
    entities: dict[str, list[str]]
    correlation_confidence: float | None = None
