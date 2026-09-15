from __future__ import annotations
import json
import logging
import time
from contextlib import contextmanager
from typing import Iterator


class Observability:
    """Small dependency-free observability helper for structured lifecycle events."""
    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger("text2sql")

    def event(self, trace_id: str, event: str, **fields) -> None:
        payload = {"trace_id": trace_id, "event": event, **fields}
        self.logger.info(json.dumps(payload, ensure_ascii=False, default=str))

    @contextmanager
    def timed(self, trace_id: str, operation: str, **fields) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.event(trace_id, "OPERATION_COMPLETED", operation=operation,
                       duration_ms=round((time.perf_counter() - start) * 1000, 2), **fields)
