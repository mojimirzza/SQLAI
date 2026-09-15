from __future__ import annotations
import uuid
from datetime import datetime, timezone

class ProposalBuilder:
    def __init__(self,store): self.store=store
    def build(self,council_result:dict,hypothesis:dict,evidence_result:dict)->dict:
        statement=hypothesis["statement"]
        target="semantic_layer" if statement.startswith("Semantic") else "kpi_or_operational_contract" if statement.startswith("Operational") else "data_quality_or_etl_contract" if statement.startswith("Data quality") else "domain_or_operational_contract"
        p={"proposal_id":f"KCP-{uuid.uuid4().hex[:12]}","council_run_id":council_result["council_run_id"],"hypothesis_id":hypothesis["hypothesis_id"],"created_at":datetime.now(timezone.utc).isoformat(),"status":"pending","reason":statement,"evidence_ids":hypothesis["supporting_evidence"],"affected_component":target,"proposed_change":f"Investigate and, only after validation, update the authoritative {target} contract implicated by the evidence.","expected_effect":"Reduce recurrence while preserving deterministic analytical behavior.","risk":"medium","rollback":"Revert the approved contract change and rerun regression and security tests.","validation_requirements":["golden questions","semantic validation","security regression","shadow/cooldown monitoring"],"approval_requirements":["human owner","risk reviewer","CI/CD"]}
        self.store.save_proposal(p); return p
