"""Release-candidate verification gate for ITXN Stage 4.

Runs repository-level checks that do not require external credentials. Checks
that depend on missing optional/runtime dependencies are reported as BLOCKED,
never silently converted to PASS.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(name: str, command: list[str]) -> tuple[str, str]:
    try:
        proc = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        return "FAIL", f"{name} timed out after 30 seconds"
    status = "PASS" if proc.returncode == 0 else "FAIL"
    output = (proc.stdout + proc.stderr).strip()
    return status, output


def _clean_runtime_artifacts() -> None:
    import shutil
    for path in ROOT.rglob("__pycache__"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    for path in ROOT.rglob("*.pyc"):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    cache = ROOT / ".pytest_cache"
    if cache.exists():
        shutil.rmtree(cache, ignore_errors=True)


def main() -> int:
    _clean_runtime_artifacts()
    checks: list[tuple[str, str, str]] = []

    status, out = run("compileall", [sys.executable, "-m", "compileall", "-q", "."])
    checks.append(("Python compileall", status, out))

    status, out = run("pytest", [sys.executable, "-m", "pytest", "-q"])
    checks.append(("pytest suite", status, out))

    status, out = run("golden", [sys.executable, "scripts/run_golden_tests.py"])
    checks.append(("deterministic aggregate golden", status, out))

    status, out = run("detail golden", [sys.executable, "scripts/run_detail_golden_tests.py"])
    checks.append(("deterministic detail/Top-N golden", status, out))

    status, out = run("security audit", [sys.executable, "scripts/run_security_audit.py"])
    checks.append(("security static audit", status, out))

    status, out = run("performance smoke", [sys.executable, "scripts/run_performance_smoke.py"])
    checks.append(("SML performance smoke", status, out))

    required = ["duckdb", "sqlglot", "openai"]
    missing = [m for m in required if importlib.util.find_spec(m) is None]
    if missing:
        checks.append((
            "runtime dependencies",
            "BLOCKED",
            "Missing in verification environment: " + ", ".join(missing),
        ))
    else:
        checks.append(("runtime dependencies", "PASS", "duckdb/sqlglot/openai import successfully"))

    canonical = ROOT / "src/api/main.py"
    canonical_text = canonical.read_text(encoding="utf-8")
    checks.append((
        "canonical API entrypoint",
        "PASS" if "main_enriched" in canonical_text else "FAIL",
        "src.api.main delegates to main_enriched" if "main_enriched" in canonical_text else "canonical entrypoint drift detected",
    ))

    src_py = [p for p in (ROOT / "src").rglob("*.py") if "__pycache__" not in p.parts]
    forbidden_refs = []
    for path in src_py:
        text = path.read_text(encoding="utf-8")
        if "from sml" in text or "import sml" in text or "from evolution" in text or "import evolution" in text:
            forbidden_refs.append(str(path.relative_to(ROOT)))
    checks.append((
        "core isolation",
        "PASS" if not forbidden_refs else "FAIL",
        "no SML/Evolution imports under src/" if not forbidden_refs else "forbidden imports: " + ", ".join(forbidden_refs),
    ))

    _clean_runtime_artifacts()
    pycache = list(ROOT.rglob("__pycache__")) + list(ROOT.rglob("*.pyc"))
    checks.append((
        "clean source tree",
        "PASS" if not pycache else "FAIL",
        "no bytecode/cache artifacts" if not pycache else f"found {len(pycache)} cache/bytecode artifacts",
    ))

    print("ITXN RELEASE-CANDIDATE GATE")
    print("=" * 72)
    for name, status, detail in checks:
        print(f"[{status:7}] {name}")
        if detail:
            print(detail[:4000])
            print()

    hard_failures = sum(status == "FAIL" for _, status, _ in checks)
    blocked = sum(status == "BLOCKED" for _, status, _ in checks)
    print(f"SUMMARY: failures={hard_failures}, blocked={blocked}")
    if hard_failures:
        return 1
    if blocked:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
