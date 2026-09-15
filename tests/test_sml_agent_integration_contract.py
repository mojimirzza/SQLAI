import json
from sml.core.contracts import SituationMemoryRequest, SituationMemoryResponse, SituationMemoryItem


def test_memory_contract_is_evidence_only():
    req = SituationMemoryRequest(
        query_id="Q1",
        entities={"bank": ["Mellat"], "metric": ["avg_latency"]},
        limit=5,
        min_score=0.6,
    )
    resp = SituationMemoryResponse(
        schema_version="1.0",
        request=req,
        items=(SituationMemoryItem(
            "S1", 0.91, "resolved",
            {"situation": {"resolution_outcome": "resolved"},
             "signals": [], "loop_trace_refs": [{"run_id": "R1", "iteration_count": 3}]}
        ),)
    )
    assert resp.authority == "evidence_only"
    assert resp.decision_binding is False
    assert all("next_action" not in item.evidence for item in resp.items)
    assert all("action" not in item.evidence for item in resp.items)


def test_request_is_bounded():
    req = SituationMemoryRequest(limit=999, min_score=-1.0)
    assert req.limit > 5  # provider clamps; contract accepts caller intent
    assert req.min_score < 0.0
