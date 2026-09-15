from __future__ import annotations

from pathlib import Path


def test_duckdb_executor_has_real_timeout_watchdog():
    source = Path("src/adapters/duckdb_executor.py").read_text(encoding="utf-8")
    assert "threading.Timer" in source
    assert "conn.interrupt()" in source
    assert "timeout_ms" in source


def test_main_path_uses_async_followup_dispatch():
    source = Path("src/core/enriched_orchestrator.py").read_text(encoding="utf-8")
    assert "trigger_suggest_async" in source
    assert "trigger_suggest(record.id)" not in source


def test_release_gate_exists_and_is_documented():
    assert Path("scripts/run_release_gate.py").exists()
    assert Path("docs/RELEASE_CANDIDATE.md").exists()
