"""
Sidecar Agent CLI — Three modes, one entry point.

Usage:
  python -m sidecar --mode report                    # Generate gap report
  python -m sidecar --mode investigate --query-id <id>  # Investigate anomaly
  python -m sidecar --mode suggest --query-id <id>      # Generate follow-ups

Environment:
  OPENAI_API_KEY    Required
  SIDECAR_CONFIG    Optional path to config.yaml (default: ./config.yaml)
"""
from __future__ import annotations
import argparse
import os
import sys
import json
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Make the core project adapters available when Sidecar is launched as a standalone CLI.
PROJECT_SRC = Path(__file__).resolve().parent.parent / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

# Load .env from parent project if present
load_dotenv(Path(__file__).parent.parent / ".env")

from core.db_reader import DBReader
from core.llm_client import LLMClient
from core.state_manager import StateManager
from agents.gap_analyst import GapAnalyst
from agents.anomaly_investigator import AnomalyInvestigator
from agents.followup_suggester import FollowupSuggester
from core.situation_memory import SituationMemoryProvider


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_path(base: Path, rel: str) -> str:
    p = Path(rel)
    if p.is_absolute():
        return str(p)
    return str(base / p)


def main():
    parser = argparse.ArgumentParser(description="Sidecar Agentic Analysis")
    parser.add_argument("--mode", choices=["report", "investigate", "suggest"],
                        required=True, help="Agent mode to run")
    parser.add_argument("--query-id", type=str, default=None,
                        help="Query UUID (required for investigate and suggest)")
    parser.add_argument("--config", type=str, default="config.yaml",
                        help="Path to config.yaml")
    args = parser.parse_args()

    if args.mode in ("investigate", "suggest") and not args.query_id:
        parser.error(f"--query-id is required for mode '{args.mode}'")

    # Load config
    config = load_config(args.config)
    paths = config.get("paths", {})
    llm_cfg = config.get("llm", {})
    thresholds = config.get("thresholds", {})

    base_dir = Path(args.config).parent

    # Initialize components
    db = DBReader(
        memory_db_path=resolve_path(base_dir, paths.get("memory_db", "../data/memory.db")),
        warehouse_db_path=resolve_path(base_dir, paths.get("warehouse_db", "../data/bank.duckdb")),
        semantic_layer_path=resolve_path(base_dir, paths.get("semantic_layer", "../src/config/semantic_layer.yaml")),
        trace_logs_dir=resolve_path(base_dir, paths.get("trace_logs_dir", "../data/trace_logs")) if paths.get("trace_logs_dir") else None,
        agent_alerts_db_path=resolve_path(base_dir, paths.get("agent_alerts_db", "../data/agent_alerts.db")) if paths.get("agent_alerts_db") else None,
    )

    llm = LLMClient(
        model=llm_cfg.get("model", "gpt-4o-mini"),
        temperature=llm_cfg.get("temperature", 0.0),
        max_tokens=llm_cfg.get("max_tokens", 2000),
    )

    state = StateManager(
        db_path=resolve_path(base_dir, paths.get("agent_state_db", "../data/agent_state.db"))
    )
    inv_cfg = thresholds.get("anomaly_investigator", {})
    situation_memory = SituationMemoryProvider(
        db_path=resolve_path(base_dir, paths.get("situation_memory_db", "../data/situation_memory.db")),
        limit=inv_cfg.get("situation_memory_limit", 5),
        min_score=inv_cfg.get("situation_memory_min_score", 0.60),
    )

    # Execute mode
    if args.mode == "report":
        gap_cfg = thresholds.get("gap_analyst", {})
        agent = GapAnalyst(
            db=db, llm=llm, state=state,
            lookback_days=gap_cfg.get("lookback_days", 7),
            min_confidence=gap_cfg.get("min_confidence", 0.70),
            min_query_count=gap_cfg.get("min_query_count", 3),
            reports_dir=resolve_path(base_dir, paths.get("reports_dir", "./reports")),
            max_steps=gap_cfg.get("max_steps", 10),
        )
        result = agent.run()
        print(f"Gap report generated: {result.get('report_path', 'N/A')}")
        print(f"Missing metrics: {result.get('missing_metrics', [])}")
        print(f"Missing dimensions: {result.get('missing_dimensions', [])}")

    elif args.mode == "investigate":
        inv_cfg = thresholds.get("anomaly_investigator", {})
        agent = AnomalyInvestigator(
            db=db, llm=llm, state=state,
            max_drilldown=inv_cfg.get("max_drilldown_queries", 5),
            reports_dir=resolve_path(base_dir, paths.get("reports_dir", "./reports")),
            max_steps=inv_cfg.get("max_steps", 10),
            situation_memory=situation_memory,
        )
        result = agent.run(args.query_id)
        if "error" in result:
            print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"Investigation complete: {result.get('report_path', 'N/A')}")
        print(f"Hypothesis: {result.get('hypothesis', {}).get('hypothesis', 'N/A')}")
        print(f"Confidence: {result.get('hypothesis', {}).get('confidence', 'N/A')}")
        print(f"Next action: {result.get('hypothesis', {}).get('next_action', 'N/A')}")

    elif args.mode == "suggest":
        sug_cfg = thresholds.get("followup_suggester", {})
        agent = FollowupSuggester(
            db=db, llm=llm, state=state,
            max_suggestions=sug_cfg.get("max_suggestions", 3),
        )
        suggestions = agent.run(args.query_id)
        print(json.dumps({"suggestions": suggestions}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
