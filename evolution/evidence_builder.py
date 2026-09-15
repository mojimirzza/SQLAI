from __future__ import annotations
import hashlib, json, uuid
from datetime import datetime, timezone
from .storage import EvolutionStore

_REQUIRED_EVIDENCE_FIELDS=("evidence_id","type","source","observed_at","observation","value","confidence","trace")

_SOURCE_RELIABILITY={"src":0.85,"agents":0.90,"sidecar":0.85,"sml":0.80,"human":0.95}

def _validate_package(pkg:dict)->list[str]:
    errors=[]
    for field in ("schema_version","package_id","created_at","trigger","context","evidence","impact","package_confidence","summary","traceability"):
        if field not in pkg: errors.append(f"missing:{field}")
    if not isinstance(pkg.get("evidence"),list) or not pkg.get("evidence"): errors.append("evidence must be non-empty list")
    for i,e in enumerate(pkg.get("evidence",[])):
        for field in _REQUIRED_EVIDENCE_FIELDS:
            if field not in e: errors.append(f"evidence[{i}].missing:{field}")
        if not (0.0 <= float(e.get("confidence",-1)) <= 1.0): errors.append(f"evidence[{i}].invalid_confidence")
        if not e.get("trace",{}).get("source_reference"): errors.append(f"evidence[{i}].missing_trace")
    return errors

class EvidenceBuilder:
    def __init__(self,situation_store,evolution_store:EvolutionStore|None=None,min_independent_sources:int=2,min_confidence:float=0.60):
        self.situation_store=situation_store; self.store=evolution_store or EvolutionStore(); self.min_independent_sources=min_independent_sources; self.min_confidence=min_confidence
    def build_for_situation(self,situation_id:str)->dict:
        data=self.situation_store.get_situation(situation_id)
        if not data: raise ValueError(f"Situation {situation_id} not found")
        s=data["situation"]; signals=data["signals"]
        source_systems=sorted({x["source_system"] for x in signals}); independent=len(source_systems)
        evidence_items=[]
        for x in signals:
            attrs=json.loads(x.get("attributes_json") or "{}")
            entities=json.loads(x.get("entities_json") or "{}")
            corr=float(x.get("correlation_score") or 0.0)
            reliability=_SOURCE_RELIABILITY.get(x["source_system"],0.75)
            confidence=max(0.0,min(1.0,0.55*reliability+0.45*corr if corr>0 else 0.75*reliability))
            observation={"signal_type":x["signal_type"],"entities":entities,"attributes":attrs,"correlation_score":corr}
            evidence_items.append({"evidence_id":f"EV-{x['signal_type']}-{x['signal_id']}","type":x["signal_type"],"source":x["source_system"],"observed_at":x["observed_at"],"observation":json.dumps(observation,ensure_ascii=False,sort_keys=True,default=str),"value":{"signal_id":x["signal_id"],"entities":entities,"attributes":attrs},"confidence":confidence,"trace":{"source_reference":x["source_reference"],"provenance":json.loads(x.get("provenance_json") or "{}")}})
        avg_conf=sum(float(x["confidence"]) for x in evidence_items)/len(evidence_items) if evidence_items else 0.0
        independence_score=min(1.0,independent/2.0); trace_score=sum(1 for x in evidence_items if x["trace"].get("source_reference"))/max(1,len(evidence_items))
        package_confidence=max(0.0,min(0.99,0.50*avg_conf+0.30*independence_score+0.20*trace_score))
        impact={"signal_count":len(signals),"independent_source_count":independent,"resolution_outcome":s.get("resolution_outcome"),"resolution_time_minutes":s.get("resolution_time_minutes")}
        pkg={"schema_version":"1.0","package_id":f"EP-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:12]}","created_at":datetime.now(timezone.utc).isoformat(),"trigger":{"type":"situation_correlated","severity":"medium","detected_at":s["created_at"]},"context":{"environment":"production","affected_capability":"operational_intelligence","time_window":{"from":s["first_signal_at"],"to":s["last_signal_at"]},"situation_id":situation_id},"evidence":evidence_items,"impact":impact,"package_confidence":package_confidence,"summary":{"title":f"Situation {situation_id}","description":s.get("narrative") or f"Correlated operational situation with {len(signals)} signals.","key_findings":[f"{len(signals)} signals",f"{independent} independent source systems"]},"traceability":{"source_count":len(signals),"independent_source_count":independent,"immutable_snapshot":True,"source_references":[x["source_reference"] for x in signals]}}
        canonical=json.dumps(pkg,ensure_ascii=False,sort_keys=True,separators=(",",":")); digest=hashlib.sha256(canonical.encode()).hexdigest(); pkg["traceability"]["evidence_hash"]=f"sha256:{digest}"
        errors=_validate_package(pkg); status="accepted" if not errors and independent>=self.min_independent_sources and package_confidence>=self.min_confidence else "rejected"
        result={"status":status,"validation_errors":errors if status=="rejected" else [],"evidence_hash":digest,"payload":{"evidence_package":pkg}}
        self.store.save_evidence(result["payload"],status,digest); return result
