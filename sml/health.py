"""Lightweight health checks for asynchronous SML deployment."""
from __future__ import annotations
import sqlite3
from pathlib import Path

def check_situation_db(path: str) -> tuple[bool, str]:
    p=Path(path)
    if not p.is_file(): return False, f"missing:{p}"
    try:
        uri=f"file:{p.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=2.0) as c:
            c.execute("SELECT 1 FROM situations LIMIT 1").fetchone()
        return True, "ok"
    except Exception as exc:
        return False, f"{type(exc).__name__}:{exc}"
