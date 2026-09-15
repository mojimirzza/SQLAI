"""Run deterministic SQL-generator golden fixtures.

This suite intentionally tests the deterministic Core layer only. It does not
exercise LLM intent extraction. Each fixture supplies an explicit canonical
intent and entity set, so failures are attributable to SQL generation or the
semantic layer rather than a hidden heuristic parser.
"""
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


def run(fixture_path: Path | None = None) -> int:
    fixture_path = fixture_path or (ROOT / "tests/golden/test_transactions.json")
    if not fixture_path.exists():
        print(f"ERROR: golden fixture not found: {fixture_path}")
        return 2

    tests = json.loads(fixture_path.read_text(encoding="utf-8"))
    generator = SQLGenerator(YAMLSemanticAdapter(str(ROOT / "src/config/semantic_layer.yaml")))

    passed = 0
    for test in tests:
        try:
            intent = Intent(
                category=test["category"],
                confidence=0.95,
                entities=test.get("entities", {}),
            )
            generated = generator.generate(intent, {})
        except Exception as exc:
            print(f"FAIL {test['id']}: generation error: {exc}")
            continue

        missing = [needle for needle in test.get("expected_sql_contains", []) if needle not in generated.sql]
        if missing:
            print(f"FAIL {test['id']}: missing {missing}")
            print(generated.sql)
            continue

        print(f"PASS {test['id']}: {test['query']}")
        passed += 1

    total = len(tests)
    print(f"\nGolden result: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(run())
