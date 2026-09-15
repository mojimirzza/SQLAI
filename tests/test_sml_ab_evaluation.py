from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "sidecar"))

from sml.react_ab_evaluation import run_ab_evaluation


def test_ab_evaluation_passes_and_memory_reduces_drilldowns(tmp_path: Path):
    report = tmp_path / "ab.json"
    result = run_ab_evaluation(report)
    assert result["decision"] == "PASS"
    assert result["memory"]["success_rate"] == 1.0
    assert result["memory"]["target_hit_rate"] == 1.0
    assert result["control"]["success_rate"] == 1.0
    assert result["control"]["target_hit_rate"] == 1.0
    assert result["memory"]["mean_drilldowns"] < result["control"]["mean_drilldowns"]
    assert result["delta"]["targeted_first_pp"] > 0
    assert json.loads(report.read_text(encoding="utf-8"))["decision"] == "PASS"
