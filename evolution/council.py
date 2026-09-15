from __future__ import annotations
import uuid, json
ROLES=("risk","tech","finance","market")

class Council:
    def __init__(self,store): self.store=store
    def deliberate(self,evidence_result:dict,hypotheses:list[dict])->dict:
        if not hypotheses: raise ValueError("No hypotheses")
        ep=evidence_result["payload"]["evidence_package"]; package_id=ep["package_id"]; run_id=f"COR-{uuid.uuid4().hex[:12]}"; evidence_by_id={e["evidence_id"]:e for e in ep.get("evidence",[])}
        totals={h["hypothesis_id"]:0.0 for h in hypotheses}; rows=[]
        for role in ROLES:
            for h in hypotheses:
                support=h.get("supporting_evidence",[]); contradict=h.get("contradictory_evidence",[])
                support_conf=sum(float(evidence_by_id[i]["confidence"]) for i in support if i in evidence_by_id)/max(1,len([i for i in support if i in evidence_by_id]))
                penalty=min(0.25,0.10*len(contradict))
                role_bias={"risk":0.03 if "Operational" in h["statement"] else 0.0,"tech":0.03 if "Semantic" in h["statement"] or "Data quality" in h["statement"] else 0.0,"finance":0.02 if "Operational" in h["statement"] else 0.0,"market":0.01 if "Operational" in h["statement"] else 0.0}[role]
                score=max(0.0,min(0.99,0.55*h["confidence"]+0.45*support_conf+role_bias-penalty))
                argument=f"{role} supports the hypothesis because {len(support)} directly linked evidence item(s) have traceable support."
                counterargument=f"{role} requires additional validation before treating the hypothesis as causal; contradictory evidence count is {len(contradict)}."
                rationale=f"score={score:.3f}; support_confidence={support_conf:.3f}; evidence_ids={support}"
                self.store.save_vote(run_id,role,h["hypothesis_id"],score,rationale); self.store.save_argument(run_id,role,h["hypothesis_id"],argument,counterargument,support); totals[h["hypothesis_id"]]+=score; rows.append({"role":role,"hypothesis_id":h["hypothesis_id"],"score":score,"argument":argument,"counterargument":counterargument,"evidence_ids":support})
        winner=max(totals,key=totals.get); resolution={"winning_hypothesis_id":winner,"roles":ROLES,"totals":totals,"arguments":rows,"method":"deterministic evidence-weighted council v1"}
        self.store.save_council(run_id,package_id,winner,resolution)
        return {"council_run_id":run_id,"winning_hypothesis_id":winner,"resolution":resolution}
