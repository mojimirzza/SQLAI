from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sml.react_ab_evaluation import run_ab_evaluation


def main():
    parser = argparse.ArgumentParser(description="Run deterministic SML/ReAct A/B evaluation")
    parser.add_argument("--output", default="reports/sml_react_ab.json")
    args = parser.parse_args()
    result = run_ab_evaluation(args.output)
    print(f"A/B decision: {result['decision']}")
    print(f"Memory mean drilldowns: {result['memory']['mean_drilldowns']:.2f}")
    print(f"Control mean drilldowns: {result['control']['mean_drilldowns']:.2f}")
    print(f"Targeted-first delta: {result['delta']['targeted_first_pp']:.1f} pp")


if __name__ == "__main__":
    main()
