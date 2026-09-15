from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class MetricDefinition:
    name: str
    sql_expression: str
    table: str
    dimensions: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    description: str = ""
    joins: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DetailFieldDefinition:
    name: str
    sql_expression: str
    alias: str
    description: str = ""


@dataclass
class DetailViewDefinition:
    name: str
    table: str
    fields: dict[str, DetailFieldDefinition] = field(default_factory=dict)
    joins: list[dict[str, Any]] = field(default_factory=list)
    default_fields: list[str] = field(default_factory=list)
    max_limit: int = 100
    description: str = ""


class SemanticLayerPort(Protocol):
    def get_metric(self, name: str) -> MetricDefinition | None: ...
    def list_metrics(self) -> list[str]: ...
    def get_detail_view(self, name: str) -> DetailViewDefinition | None: ...
    def list_detail_views(self) -> list[str]: ...
    def get_join(self, table: str) -> dict[str, Any] | None: ...
