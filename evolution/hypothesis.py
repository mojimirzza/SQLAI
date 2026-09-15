from __future__ import annotations
import uuid, json

class HypothesisGenerator:
    """Deterministic, evidence-driven hypothesis builder behind RFC-001."""
    def __init__(self,store): self.store=store
    def generate(self,evidence_result:dict)->list[dict]:
        ep=evidence_result["payload"]["evidence_package"]; evidences=ep.get("evidence",[]); by_type={}
        for e in evidences: by_type.setdefault(e["type"],[]).append(e)
        candidates=[]
        if any(k in by_type for k in ("alert","investigation","pattern_family","pattern_drift")):
            ids=[e["evidence_id"] for k in ("alert","investigation","pattern_family","pattern_drift") for e in by_type.get(k,[])]
            candidates.append(("Operational condition changed","The correlated operational signals indicate a change in runtime behavior that warrants validation against KPI and resolution history.",ids,"Validate KPI state, incident outcome, and resolution timeline."))
        semantic_text=" ".join(e["observation"] for e in by_type.get("query",[])+by_type.get("investigation",[])).lower()
        if any(x in semantic_text for x in ("semantic","mapping","dimension","metric")) or "query" in by_type:
            ids=[e["evidence_id"] for e in by_type.get("query",[]) + by_type.get("investigation",[])]
            candidates.append(("Semantic/domain mapping gap","The affected queries may expose a mismatch between observed business concepts and the authoritative semantic contract.",ids,"Compare affected intent, metric, dimensions, filters, and semantic-layer constraints."))
        if any(k in by_type for k in ("dq","data_quality","etl")) or "data quality" in semantic_text:
            ids=[e["evidence_id"] for k in ("dq","data_quality","etl") for e in by_type.get(k,[])]
            candidates.append(("Data quality or upstream regression","The situation may be explained by degraded upstream data quality or ETL output.",ids,"Inspect DQ gates, ETL status, and affected time window."))
        if not candidates:
            candidates=[("Operational or domain change","Available evidence is insufficient to distinguish operational change from a domain-model issue.",[e["evidence_id"] for e in evidences],"Collect an additional independent signal before proposing a production change." )]
        out=[]
        for statement,detail,supporting,plan in candidates:
            avg=sum(float(e["confidence"]) for e in evidences if e["evidence_id"] in supporting)/max(1,len(supporting)); conf=max(0.40,min(0.95,avg))
            h={"hypothesis_id":f"HYP-{uuid.uuid4().hex[:12]}","package_id":ep["package_id"],"statement":statement,"description":detail,"confidence":conf,"assumptions":[],"supporting_evidence":supporting,"contradictory_evidence":[],"validation_plan":plan,"status":"candidate"}
            self.store.save_hypothesis(h); out.append(h)
        return out
