from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sidecar"))
sys.path.insert(0, str(ROOT))

from sml.storage import SituationStore
from sml.correlator import SituationCorrelator
from sml.core.models import Signal
from sidecar.core.situation_memory import SituationMemoryProvider


def _seed_situation(path: Path):
    store = SituationStore(str(path))
    t = datetime.now(timezone.utc).replace(microsecond=0)
    signal = Signal("q-hist", "query", t, "memory", "memory.db", {"bank": ["Mellat"], "server": ["SRV-A"], "metric": ["avg_latency"]})
    store.create_situation("S-HIST", signal, signal.entities, 0.95, status="resolved")
    return t


def test_provider_is_evidence_only_and_read_only(tmp_path: Path):
    db = tmp_path / "situation_memory.db"
    _seed_situation(db)
    before = db.stat().st_mtime_ns
    provider = SituationMemoryProvider(str(db), limit=5, min_score=0.6)
    out = provider.retrieve(query_id="q-current", entities={"bank": ["Mellat"], "server": ["SRV-A"], "metric": ["avg_latency"]})
    assert out["status"] == "ok"
    assert out["authority"] == "evidence_only"
    assert out["decision_binding"] is False
    assert out["items"]
    assert not any("next_action" in item["evidence"] for item in out["items"])
    assert db.stat().st_mtime_ns == before


def test_provider_failure_bypasses(tmp_path: Path):
    provider = SituationMemoryProvider(str(tmp_path / "missing.db"))
    out = provider.retrieve(query_id="q1", entities={"metric": ["latency"]})
    assert out["status"] == "bypassed"
    assert out["authority"] == "evidence_only"
    assert out["decision_binding"] is False
    assert out["items"] == []


def test_prompt_marks_memory_untrusted_and_non_binding(tmp_path: Path):
    db = tmp_path / "situation_memory.db"
    _seed_situation(db)
    provider = SituationMemoryProvider(str(db))
    result = provider.retrieve(query_id="q-current", entities={"bank": ["Mellat"], "server": ["SRV-A"], "metric": ["avg_latency"]})
    prompt = provider.as_prompt_context(result)
    assert "UNTRUSTED HISTORICAL EVIDENCE" in prompt
    assert "decision_binding: false" in prompt
    assert "do not execute" in prompt.lower()


def test_provider_is_bounded(tmp_path: Path):
    db = tmp_path / "situation_memory.db"
    _seed_situation(db)
    provider = SituationMemoryProvider(str(db), limit=999, min_score=-1)
    assert provider.limit == 20
    assert provider.min_score == 0.0


def test_investigator_source_wires_memory_into_react():
    source = (ROOT / "sidecar" / "agents" / "anomaly_investigator.py").read_text(encoding="utf-8")
    assert "SituationMemoryProvider" in source
    assert "_retrieve_situation_memory" in source
    assert 'name="read_situation_memory"' in source
    assert "memory_result = self._retrieve_situation_memory" in source
    assert "_build_task(record, sql, entities, metric, alert_context, memory_result)" in source
