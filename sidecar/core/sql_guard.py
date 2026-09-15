from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SQLGuardDecision:
    allowed: bool
    reason: str = ""
    tables: tuple[str, ...] = ()


class SidecarSQLGuard:
    """Defensive gate for agent-proposed drill-down SQL."""
    def __init__(self, validator, allowed_tables: set[str] | None = None, max_sql_length: int = 8000):
        self.validator = validator
        self.allowed_tables = {t.lower() for t in (allowed_tables or set())}
        self.max_sql_length = max_sql_length

    def check(self, sql: str) -> SQLGuardDecision:
        if not sql or len(sql) > self.max_sql_length:
            return SQLGuardDecision(False, "SQL is empty or exceeds the configured length limit.")
        validation = self.validator.validate(sql)
        if not validation.is_valid:
            return SQLGuardDecision(False, "; ".join(validation.errors) or "SQL validation failed")
        tables = tuple(str(t) for t in validation.tables_accessed)
        if self.allowed_tables and any(t.lower() not in self.allowed_tables for t in tables):
            return SQLGuardDecision(False, "Drill-down references a table outside the sidecar allow-list.", tables)
        return SQLGuardDecision(True, tables=tables)
