from __future__ import annotations
import json, sqlite3
from pathlib import Path

class EvolutionStore:
    def __init__(self, db_path: str = "data/knowledge_evolution.db"):
        self.db_path=db_path; Path(db_path).parent.mkdir(parents=True,exist_ok=True); self.init_db()
    def init_db(self):
        with sqlite3.connect(self.db_path) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS evidence_packages (package_id TEXT PRIMARY KEY,schema_version TEXT NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL,payload_json TEXT NOT NULL,evidence_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS hypotheses (hypothesis_id TEXT PRIMARY KEY,package_id TEXT NOT NULL,statement TEXT NOT NULL,confidence REAL NOT NULL,assumptions_json TEXT NOT NULL,supporting_json TEXT NOT NULL,contradictory_json TEXT NOT NULL,validation_plan TEXT NOT NULL,status TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS council_runs (council_run_id TEXT PRIMARY KEY,package_id TEXT NOT NULL,created_at TEXT NOT NULL,winning_hypothesis_id TEXT,resolution_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS council_votes (council_run_id TEXT NOT NULL,role TEXT NOT NULL,hypothesis_id TEXT NOT NULL,score REAL NOT NULL,rationale TEXT NOT NULL,PRIMARY KEY(council_run_id,role,hypothesis_id));
            CREATE TABLE IF NOT EXISTS council_arguments (council_run_id TEXT NOT NULL,role TEXT NOT NULL,hypothesis_id TEXT NOT NULL,argument TEXT NOT NULL,counterargument TEXT NOT NULL,evidence_ids_json TEXT NOT NULL,PRIMARY KEY(council_run_id,role,hypothesis_id));
            CREATE TABLE IF NOT EXISTS proposals (proposal_id TEXT PRIMARY KEY,council_run_id TEXT NOT NULL,hypothesis_id TEXT NOT NULL,created_at TEXT NOT NULL,status TEXT NOT NULL,payload_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS governance_decisions (proposal_id TEXT PRIMARY KEY,decision TEXT NOT NULL,actor TEXT NOT NULL,decided_at TEXT NOT NULL,reason TEXT);
            """)
    def save_evidence(self,payload:dict,status:str,evidence_hash:str):
        with sqlite3.connect(self.db_path) as c:c.execute("INSERT OR REPLACE INTO evidence_packages VALUES (?,?,?,?,?,?)",(payload["evidence_package"]["package_id"],payload["evidence_package"]["schema_version"],payload["evidence_package"]["created_at"],status,json.dumps(payload,ensure_ascii=False,sort_keys=True),evidence_hash))
    def save_hypothesis(self,h:dict):
        with sqlite3.connect(self.db_path) as c:c.execute("INSERT OR REPLACE INTO hypotheses VALUES (?,?,?,?,?,?,?,?,?)",(h["hypothesis_id"],h["package_id"],h["statement"],h["confidence"],json.dumps(h.get("assumptions",[]),ensure_ascii=False),json.dumps(h.get("supporting_evidence",[]),ensure_ascii=False),json.dumps(h.get("contradictory_evidence",[]),ensure_ascii=False),h.get("validation_plan",""),h.get("status","candidate")))
    def save_council(self,run_id,package_id,winner,resolution):
        with sqlite3.connect(self.db_path) as c:c.execute("INSERT INTO council_runs VALUES (?,?,?,?,?)",(run_id,package_id,datetime_now(),winner,json.dumps(resolution,ensure_ascii=False,sort_keys=True)))
    def save_vote(self,run_id,role,hypothesis_id,score,rationale):
        with sqlite3.connect(self.db_path) as c:c.execute("INSERT OR REPLACE INTO council_votes VALUES(?,?,?,?,?)",(run_id,role,hypothesis_id,score,rationale))
    def save_argument(self,run_id,role,hypothesis_id,argument,counterargument,evidence_ids):
        with sqlite3.connect(self.db_path) as c:c.execute("INSERT OR REPLACE INTO council_arguments VALUES(?,?,?,?,?,?)",(run_id,role,hypothesis_id,argument,counterargument,json.dumps(evidence_ids,ensure_ascii=False)))
    def save_proposal(self,p):
        with sqlite3.connect(self.db_path) as c:c.execute("INSERT OR REPLACE INTO proposals VALUES(?,?,?,?,?,?)",(p["proposal_id"],p["council_run_id"],p["hypothesis_id"],p["created_at"],p.get("status","pending"),json.dumps(p,ensure_ascii=False,sort_keys=True)))

def datetime_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
