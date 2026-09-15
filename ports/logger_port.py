from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass
class LogEntry:
    trace_id: str
    event: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LoggerPort(Protocol):
    def log(self, entry: LogEntry) -> None: ...
