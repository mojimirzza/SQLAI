from __future__ import annotations
import json
from dataclasses import asdict
from typing import Any

from .core.contracts import SituationMemoryRequest, SituationMemoryResponse, SituationMemoryItem
from .core.normalizer import normalize_entities


def _entity_score(a: dict[str, list[str]], b: dict[str, list[str]]) -> float:
    aa = normalize_entities(a)
    bb = normalize_entities(b)
    keys = set(aa) | set(bb)
    if not keys:
        return 0.0
    matched = 0.0
    denom = 0.0
    weights = {"query_id": 1.0, "server": 1.0, "bank": 1.0, "metric": 0.9, "kpi_name": 0.9, "device_category": 0.5}
    for key in keys:
        av, bv = aa.get(key, set()), bb.get(key, set())
        if not av or not bv:
            continue
        w = weights.get(key, 0.25)
        denom += w
        if av & bv:
            matched += w
    return matched / denom if denom else 0.0


class SituationMemoryRetriever:
    """Deterministic historical retrieval; returns context, never actions."""

    def __init__(self, store):
        self.store = store

    def retrieve(self, request: SituationMemoryRequest) -> SituationMemoryResponse:
        limit = max(1, min(int(request.limit), 20))
        min_score = max(0.0, min(1.0, float(request.min_score)))
        target_entities = dict(request.entities or {})
        if request.query_id:
            target_entities.setdefault("query_id", []).append(request.query_id)

        items: list[SituationMemoryItem] = []
        for row in self.store.recent_situations(5000):
            sid = row["situation_id"]
            if request.current_situation_id and sid == request.current_situation_id:
                continue
            score = _entity_score(target_entities, json.loads(row.get("entities_json") or "{}"))
            if score < min_score:
                continue
            data = self.store.get_situation(sid)
            if not data:
                continue
            signals = data["signals"]
            loop_refs = self.store.get_loop_refs(sid)
            evidence = {
                "situation": {
                    "status": row["status"],
                    "first_signal_at": row["first_signal_at"],
                    "last_signal_at": row["last_signal_at"],
                    "entities": json.loads(row["entities_json"] or "{}"),
                    "correlation_confidence": row["correlation_confidence"],
                    "pattern_family_id": row["pattern_family_id"],
                    "pattern_drift_score": row["pattern_drift_score"],
                    "resolution_action": row["resolution_action"],
                    "resolution_outcome": row["resolution_outcome"],
                    "resolution_time_minutes": row["resolution_time_minutes"],
                },
                "signals": [
                    {"type": s["signal_type"], "id": s["signal_id"], "observed_at": s["observed_at"], "source_system": s["source_system"], "source_reference": s["source_reference"], "correlation_score": s["correlation_score"]}
                    for s in signals
                ],
                "loop_trace_refs": loop_refs,
            }
            items.append(SituationMemoryItem(sid, round(score, 4), row["status"], evidence))
        items.sort(key=lambda x: (-x.score, x.situation_id))
        return SituationMemoryResponse(
            schema_version="1.0",
            request=request,
            items=tuple(items[:limit]),
        )
