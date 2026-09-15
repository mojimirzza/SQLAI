from __future__ import annotations
import json, sqlite3, sys, importlib.util
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"src"))

from sml.storage import SituationStore
from sml.correlator import SituationCorrelator
from sml.core.models import Signal
from evolution.storage import EvolutionStore
from evolution.evidence_builder import EvidenceBuilder
from evolution.hypothesis import HypothesisGenerator
from evolution.council import Council
from evolution.proposals import ProposalBuilder
from governance.store import Governance

def make_signal(i,source,stype,when,entities):
    return Signal(i,stype,when,source,f"{source}:{stype}:{i}",entities=entities,attributes={"test":True},provenance={"fixture":True})

def test_situation_can_hold_many_signals_and_edges(tmp_path):
    store=SituationStore(str(tmp_path/"situation.db")); t=datetime.now(timezone.utc)
    s1=make_signal("q1","src","query",t,{"server":["tehran-01"],"metric":["latency"]})
    s2=make_signal("a1","agents","alert",t+timedelta(minutes=1),{"server":["tehran-01"],"metric":["latency"]})
    s3=make_signal("i1","sidecar","investigation",t+timedelta(minutes=2),{"query_id":["q1"]})
    store.create_situation("S1",s1,s1.entities,0.9); store.attach_signal("S1",s2,0.9); store.attach_signal("S1",s3,0.95)
    got=store.get_situation("S1"); assert got["situation"]["signal_count"]==3; assert len(got["events"])>=4
    store.add_edge("S1","S2","temporal_proximity",0.72)
    with sqlite3.connect(store.db_path) as c: assert c.execute("SELECT COUNT(*) FROM situation_edges").fetchone()[0]==1

def test_evidence_contract_is_rich_and_validated(tmp_path):
    ss=SituationStore(str(tmp_path/"situation.db")); es=EvolutionStore(str(tmp_path/"evolution.db")); t=datetime.now(timezone.utc)
    ss.create_situation("S1",make_signal("q1","src","query",t,{"metric":["latency"]}),{"metric":["latency"]},0.8)
    ss.attach_signal("S1",make_signal("a1","agents","alert",t+timedelta(minutes=1),{"metric":["latency"]}),0.9)
    out=EvidenceBuilder(ss,es).build_for_situation("S1"); assert out["status"]=="accepted"
    ep=out["payload"]["evidence_package"]; assert ep["traceability"]["independent_source_count"]==2
    assert all("value" in e and "trace" in e for e in ep["evidence"])

def test_hypothesis_and_council_are_evidence_driven(tmp_path):
    ss=SituationStore(str(tmp_path/"situation.db")); es=EvolutionStore(str(tmp_path/"evolution.db")); t=datetime.now(timezone.utc)
    ss.create_situation("S1",make_signal("q1","src","query",t,{"metric":["latency"]}),{"metric":["latency"]},0.8)
    ss.attach_signal("S1",make_signal("a1","agents","alert",t+timedelta(minutes=1),{"metric":["latency"]}),0.9)
    ss.attach_signal("S1",make_signal("i1","sidecar","investigation",t+timedelta(minutes=2),{"query_id":["q1"]}),0.85)
    ev=EvidenceBuilder(ss,es).build_for_situation("S1"); hyps=HypothesisGenerator(es).generate(ev); assert hyps
    council=Council(es).deliberate(ev,hyps); assert council["winning_hypothesis_id"] in {h["hypothesis_id"] for h in hyps}
    assert council["resolution"]["arguments"]
    proposal=ProposalBuilder(es).build(council,next(h for h in hyps if h["hypothesis_id"]==council["winning_hypothesis_id"]),ev); assert proposal["status"]=="pending"
    gov=Governance(es); assert gov.approve(proposal["proposal_id"],"human-reviewer")["decision"]=="approved"

def test_pattern_family_lifecycle_requires_human_validation(tmp_path):
    from datetime import timedelta
    store=SituationStore(str(tmp_path/"situation.db")); family={"family_id":"fam-x","signature":{"metric":["latency"]},"stage":"SHADOW","total_occurrences":10,"successful_resolutions":10,"success_rate":1.0,"wilson_lower_bound":0.722,"first_seen":"2026-08-01T00:00:00+00:00","last_seen":"2026-08-01T00:10:00+00:00","avg_resolution_time_minutes":4.0}
    store.upsert_pattern_family(family)
    store.transition_family("fam-x","VALIDATED","reviewer","human validation")
    with sqlite3.connect(store.db_path) as c:
        old=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()
        c.execute("UPDATE pattern_families SET validated_at=? WHERE family_id=?",(old,"fam-x"))
    active=store.transition_family("fam-x","ACTIVE","reviewer","activation")
    assert active["stage"]=="ACTIVE"

def test_canonical_api_entrypoint_uses_enriched_app():
    if importlib.util.find_spec("openai") is None:
        pytest.skip("openai is required to import the canonical API entrypoint")
    import api.main as main
    import api.main_enriched as enriched
    assert main.app is enriched.app
