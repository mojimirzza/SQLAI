from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
from .storage import SituationStore

def wilson_lower_bound(successes:int,total:int,z:float=1.96)->float:
    if total<=0:return 0.0
    p=successes/total
    denom=1+z*z/total
    centre=p+z*z/(2*total)
    margin=z*((p*(1-p)+z*z/(4*total))/total)**0.5
    return max(0.0,(centre-margin)/denom)

class PatternAnalyzer:
    def __init__(self, store:SituationStore, output_json:str="data/pattern_families.json", prediction_jsonl:str="data/situation_predictions.jsonl"):
        self.store=store; self.output_json=output_json; self.prediction_jsonl=prediction_jsonl

    def _signature(self,s):
        e=json.loads(s["entities_json"] or "{}")
        return tuple(sorted((k, tuple(sorted(str(x).lower() for x in v))) for k,v in e.items() if v))

    def _drift(self, s, family_signature):
        a={f"{k}={v}" for k,vs in self._signature(s) for v in vs}
        b={f"{k}={v}" for k,vs in family_signature for v in vs}
        if not a and not b:return 0.0
        return 1.0-len(a&b)/max(1,len(a|b))

    def run(self)->dict:
        rows=self.store.recent_situations(5000); groups=defaultdict(list)
        for s in rows:
            sig=self._signature(s); import hashlib
            key=hashlib.sha1(repr(sig).encode()).hexdigest()[:12]; groups[key].append(s)
        families=[]; predictions=[]
        for key, group in groups.items():
            sig=self._signature(group[0]); family_id=f"fam-{key}"
            total=len(group); resolved=sum(1 for x in group if x.get("resolution_outcome")=="resolved")
            success=resolved/total if total else 0.0; lb=wilson_lower_bound(resolved,total)
            persisted=self.store.get_pattern_family(family_id)
            stage=persisted["stage"] if persisted else ("SHADOW" if total>=5 and lb>=0.65 else "CANDIDATE")
            if stage in ("CANDIDATE","SHADOW") and total>=5 and lb>=0.65:
                stage="SHADOW"
            avg_minutes=sum(float(x["resolution_time_minutes"] or 0) for x in group)/resolved if resolved else 0.0
            family={"family_id":family_id,"signature":{k:list(vs) for k,vs in sig},"stage":stage,"total_occurrences":total,"successful_resolutions":resolved,"success_rate":success,"wilson_lower_bound":lb,"first_seen":min(x["first_signal_at"] for x in group),"last_seen":max(x["last_signal_at"] for x in group),"avg_resolution_time_minutes":avg_minutes}
            self.store.upsert_pattern_family(family); families.append(family)
            latest=max(group,key=lambda x:x["last_signal_at"]); drift=self._drift(latest,sig)
            self.store.upsert_pattern_fields(latest["situation_id"],family_id,drift)
            self.store.add_family_edges(family_id, latest["situation_id"], 1.0-max(0.0,min(1.0,drift)))
            if drift>0.40:
                predictions.append({"type":"pattern_drift","situation_id":latest["situation_id"],"family_id":family_id,"confidence":1.0-drift,"recommended_review":True,"drift_score":drift})
        Path(self.output_json).parent.mkdir(parents=True,exist_ok=True); Path(self.output_json).write_text(json.dumps({"families":families},ensure_ascii=False,indent=2),encoding="utf-8")
        if predictions:
            Path(self.prediction_jsonl).parent.mkdir(parents=True,exist_ok=True)
            with open(self.prediction_jsonl,"a",encoding="utf-8") as f:
                for p in predictions:f.write(json.dumps(p,ensure_ascii=False)+"\n")
        return {"families":len(families),"predictions":len(predictions)}

    def validate_family(self,family_id:str, actor:str="human", reason:str="")->dict:
        return self.store.transition_family(family_id,"VALIDATED",actor,reason)

    def activate_family(self,family_id:str, actor:str="human", reason:str="")->dict:
        return self.store.transition_family(family_id,"ACTIVE",actor,reason)
