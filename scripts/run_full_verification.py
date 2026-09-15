"""Strict full verification wrapper.

A release verification run is successful only when every hard check passes and
no required runtime dependency/environment check is blocked.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    proc = subprocess.run(
        [sys.executable, "scripts/run_release_gate.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    print(output, end="")

    blocked = False
    failures = False
    for line in output.splitlines():
        if line.startswith("SUMMARY:"):
            blocked = "blocked=0" not in line
            failures = "failures=0" not in line

    if proc.returncode != 0 or failures or blocked:
        print("FULL VERIFICATION: FAIL")
        if blocked:
            print("Reason: one or more required verification checks are BLOCKED.")
        return 1

    print("FULL VERIFICATION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
