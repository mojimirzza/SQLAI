from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    normalized_sql: str | None = None


class SQLValidatorPort(Protocol):
    def validate(self, sql: str) -> ValidationResult: ...
