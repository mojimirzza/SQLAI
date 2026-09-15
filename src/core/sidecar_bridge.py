"""
Sidecar Bridge — Lightweight integration for the main API.
No heavy imports. Uses subprocess or direct calls depending on mode.
"""
from __future__ import annotations
import os
import sys
import json
import subprocess
from pathlib import Path

# Sidecar root relative to src/
SIDECAR_ROOT = Path(__file__).parent.parent.parent / "sidecar"


def trigger_suggest(query_id: str, timeout: float = 5.0) -> list[str]:
    """
    Trigger follow-up suggestion for a query.
    Returns list of suggestion strings.
    Safe to call synchronously (fast, ~1-2s).
    """
    main_py = SIDECAR_ROOT / "main.py"
    if not main_py.exists():
        return []
    try:
        result = subprocess.run(
            [sys.executable, str(main_py), "--mode", "suggest", "--query-id", query_id],
            capture_output=True, text=True, timeout=timeout, cwd=str(SIDECAR_ROOT)
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("suggestions", [])
    except Exception:
        pass
    return []


def trigger_suggest_async(query_id: str) -> None:
    """Fire-and-forget follow-up generation; never block the request path."""
    main_py = SIDECAR_ROOT / "main.py"
    if not main_py.exists():
        return
    cmd = [sys.executable, str(main_py), "--mode", "suggest", "--query-id", query_id]
    try:
        subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            cwd=str(SIDECAR_ROOT), start_new_session=True
        )
    except Exception:
        return


def trigger_investigate(query_id: str, async_run: bool = True) -> str | None:
    """
    Trigger anomaly investigation for a query.
    By default runs async (non-blocking) since investigation takes 5-10s.
    Returns report path if sync, None if async.
    """
    main_py = SIDECAR_ROOT / "main.py"
    if not main_py.exists():
        return None
    cmd = [sys.executable, str(main_py), "--mode", "investigate", "--query-id", query_id]
    if async_run:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(SIDECAR_ROOT))
        return None
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0, cwd=str(SIDECAR_ROOT))
        if result.returncode == 0:
            # Parse report path from stdout
            for line in result.stdout.split("\n"):
                if "Investigation complete:" in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None


def trigger_report() -> str | None:
    """
    Trigger gap analysis report generation.
    Typically called from cron, not API.
    Returns report path.
    """
    main_py = SIDECAR_ROOT / "main.py"
    if not main_py.exists():
        return None
    try:
        result = subprocess.run(
            [sys.executable, str(main_py), "--mode", "report"],
            capture_output=True, text=True, timeout=60.0, cwd=str(SIDECAR_ROOT)
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "Gap report generated:" in line:
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return None
