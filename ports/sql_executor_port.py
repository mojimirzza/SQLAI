from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ExecutionResult:
    success: bool
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    error: str | None = None


class SQLExecutorPort(Protocol):
    def execute(self, sql: str) -> ExecutionResult: ...
