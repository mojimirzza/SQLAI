"""Resilient asynchronous SML worker with bounded backoff and graceful shutdown."""
from __future__ import annotations
import json, logging, signal, time
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger("sml.worker")

@dataclass
class WorkerStats:
    runs: int = 0
    failures: int = 0
    signals_seen: int = 0
    created: int = 0
    matches: int = 0
    last_error: str | None = None

class ResilientLoop:
    def __init__(self, run_once: Callable[[], dict], interval_seconds: int = 60, max_backoff_seconds: int = 300):
        self.run_once = run_once
        self.interval_seconds = max(1, int(interval_seconds))
        self.max_backoff_seconds = max(self.interval_seconds, int(max_backoff_seconds))
        self.stop_requested = False
        self.stats = WorkerStats()

    def stop(self, *_):
        self.stop_requested = True
        log.info("worker_stop_requested")

    def run(self) -> WorkerStats:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        backoff = self.interval_seconds
        while not self.stop_requested:
            started = time.monotonic()
            try:
                result = self.run_once() or {}
                self.stats.runs += 1
                self.stats.signals_seen += int(result.get("signals_seen", 0) or 0)
                self.stats.created += int(result.get("created", 0) or 0)
                self.stats.matches += int(result.get("matches", 0) or 0)
                self.stats.last_error = None
                backoff = self.interval_seconds
                log.info("sml_cycle %s", json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
            except Exception as exc:  # worker boundary: never kill the process on one bad cycle
                self.stats.failures += 1
                self.stats.last_error = f"{type(exc).__name__}: {exc}"
                log.exception("sml_cycle_failed")
                backoff = min(self.max_backoff_seconds, max(self.interval_seconds, backoff * 2))
            elapsed = time.monotonic() - started
            sleep_for = max(0.0, backoff - elapsed)
            if sleep_for:
                time.sleep(sleep_for)
        log.info("worker_stopped %s", json.dumps(self.stats.__dict__, sort_keys=True))
        return self.stats
