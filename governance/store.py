from __future__ import annotations
import sqlite3
from datetime import datetime, timezone
from evolution.storage import EvolutionStore

class Governance:
    """Human gate. No automatic approval and no production mutation."""
    def __init__(self, store:EvolutionStore|None=None): self.store=store or EvolutionStore()
    def approve(self,proposal_id:str,actor:str,reason:str=""): return self._decide(proposal_id,"approved",actor,reason)
    def reject(self,proposal_id:str,actor:str,reason:str=""): return self._decide(proposal_id,"rejected",actor,reason)
    def _decide(self,proposal_id,decision,actor,reason):
        if not actor: raise ValueError("actor is required")
        with sqlite3.connect(self.store.db_path) as c:
            row=c.execute("SELECT status FROM proposals WHERE proposal_id=?",(proposal_id,)).fetchone()
            if not row: raise ValueError(f"Proposal not found: {proposal_id}")
            existing=c.execute("SELECT decision FROM governance_decisions WHERE proposal_id=?",(proposal_id,)).fetchone()
            if existing: raise ValueError(f"Proposal already decided: {proposal_id}")
            c.execute("INSERT INTO governance_decisions VALUES(?,?,?,?,?)",(proposal_id,decision,actor,datetime.now(timezone.utc).isoformat(),reason))
            c.execute("UPDATE proposals SET status=? WHERE proposal_id=?",(decision,proposal_id)); c.commit()
        return {"proposal_id":proposal_id,"decision":decision,"actor":actor}
