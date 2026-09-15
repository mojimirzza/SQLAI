from __future__ import annotations
import argparse
from sml.storage import SituationStore
from .storage import EvolutionStore
from .evidence_builder import EvidenceBuilder
from .hypothesis import HypothesisGenerator
from .council import Council
from .proposals import ProposalBuilder

def main():
    p=argparse.ArgumentParser(description="RFC-001 Evidence → Hypothesis → Council")
    p.add_argument("--situation-id",required=True)
    p.add_argument("--situation-db",default="data/situation_memory.db")
    p.add_argument("--evolution-db",default="data/knowledge_evolution.db")
    args=p.parse_args()
    ss=SituationStore(args.situation_db); es=EvolutionStore(args.evolution_db)
    ev=EvidenceBuilder(ss,es).build_for_situation(args.situation_id)
    if ev["status"]!="accepted":
        print({"status":"evidence_rejected","reason":"insufficient independent evidence","evidence":ev}); return
    hyps=HypothesisGenerator(es).generate(ev); council=Council(es).deliberate(ev,hyps)
    winner=next(h for h in hyps if h["hypothesis_id"]==council["winning_hypothesis_id"])
    proposal=ProposalBuilder(es).build(council,winner,ev)
    print({"evidence":ev,"hypotheses":hyps,"council":council,"proposal":proposal})
if __name__=="__main__": main()
