from __future__ import annotations
import argparse, os, json
from .storage import SituationStore
from .correlator import SituationCorrelator
from .pattern_analyzer import PatternAnalyzer

def main():
    p=argparse.ArgumentParser(description="ITXN Situation Memory Layer")
    p.add_argument("--once",action="store_true")
    p.add_argument("--analyze",action="store_true")
    p.add_argument("--loop", action="store_true", help="Continuously run the correlator")
    p.add_argument("--interval-seconds", type=int, default=60, help="Loop interval for --loop")
    p.add_argument("--validate-family")
    p.add_argument("--activate-family")
    p.add_argument("--actor",default="human")
    p.add_argument("--reason",default="")
    p.add_argument("--memory-db",default=os.getenv("SML_MEMORY_DB","data/memory.db"))
    p.add_argument("--alerts-db",default=os.getenv("SML_ALERTS_DB","data/agent_alerts.db"))
    p.add_argument("--state-db",default=os.getenv("SML_STATE_DB","data/agent_state.db"))
    p.add_argument("--situation-db",default=os.getenv("SML_SITUATION_DB","data/situation_memory.db"))
    args=p.parse_args(); store=SituationStore(args.situation_db); analyzer=PatternAnalyzer(store)
    if args.validate_family:
        print(json.dumps(analyzer.validate_family(args.validate_family,args.actor,args.reason),ensure_ascii=False)); return
    if args.activate_family:
        print(json.dumps(analyzer.activate_family(args.activate_family,args.actor,args.reason),ensure_ascii=False)); return
    if args.analyze:
        print(json.dumps(analyzer.run(),ensure_ascii=False)); return
    correlator = SituationCorrelator(store,args.memory_db,args.alerts_db,args.state_db)
    if args.loop:
        import logging
        from .worker import ResilientLoop
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        ResilientLoop(correlator.run_once, interval_seconds=args.interval_seconds).run()
    result=correlator.run_once(); print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__": main()
