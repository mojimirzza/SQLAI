"""Run deterministic golden fixtures for detail / Top-N SQL generation."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "src"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from core.models import Intent
from core.sql_generator import SQLGenerator
from adapters.yaml_semantic_adapter import YAMLSemanticAdapter


def run() -> int:
    fixture_path = ROOT / "tests/golden/test_detail_topn.json"
    tests = json.loads(fixture_path.read_text(encoding="utf-8"))
    generator = SQLGenerator(YAMLSemanticAdapter(str(ROOT / "src/config/semantic_layer.yaml")))
    passed = 0
    for test in tests:
        try:
            intent = Intent(
                category=test["category"],
                confidence=0.95,
                query_type=test["query_type"],
                entities=test.get("entities", {}),
            )
            sql = generator.generate(intent, {}).sql
        except Exception as exc:
            print(f"FAIL {test['id']}: generation error: {exc}")
            continue
        missing = [x for x in test.get("expected_sql_contains", []) if x not in sql]
        forbidden = [x for x in test.get("expected_sql_not_contains", []) if x in sql]
        if missing or forbidden:
            print(f"FAIL {test['id']}: missing={missing} forbidden={forbidden}")
            print(sql)
            continue
        if any(token in sql.upper() for token in ("SUM(", "AVG(", "COUNT(")) or "GROUP BY" in sql.upper():
            print(f"FAIL {test['id']}: detail SQL contains aggregate/grouping syntax")
            print(sql)
            continue
        print(f"PASS {test['id']}: {test['query']}")
        passed += 1
    print(f"\nDetail/Top-N golden result: {passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(run())
