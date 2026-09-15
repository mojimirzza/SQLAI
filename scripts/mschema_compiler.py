"""Build-time M-Schema compiler for DuckDB/SQLite.

The compiler is intentionally build-time: generated metadata is written to an
artifact and loaded by the application at startup. Runtime query processing
never introspects the production database.

Usage examples:
    python scripts/mschema_compiler.py --db data/bank.duckdb
    python scripts/mschema_compiler.py --db data/memory.db --output src/config/mschema.yaml

The compiler combines physical metadata with the ITXN semantic layer. Real
sample values are opt-in and allow-listed; by default no raw database samples
are copied into the artifact.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path
from typing import Any

import yaml

SAMPLE_ALLOWLIST = {
    "dim_server": ["server_name", "server_type", "location"],
    "dim_terminal": ["device_category", "entry_mode_desc"],
    "dim_status": ["lifecycle_stage"],
    "dim_date": ["month_name", "day_name"],
    "dim_time": ["am_pm", "time_of_day"],
}

SYNTHETIC = {
    "fact_transaction": {
        "switch_latency_ms": ["45", "120", "847", "2300"],
        "txnamt": ["15000.00", "250000.50", "75.00"],
    }
}

_IDENT = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b")
_EQ = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b")


def _qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _load_semantic(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _semantic_descriptions(semantic: dict[str, Any], table: str, column: str) -> str:
    # Prefer explicit table/column descriptions when present.
    table_meta = semantic.get("tables", {}).get(table, {})
    if isinstance(table_meta, dict):
        col_meta = table_meta.get("columns", {})
        if isinstance(col_meta, dict):
            value = col_meta.get(column)
            if isinstance(value, dict) and value.get("description"):
                return str(value["description"])
            if isinstance(value, str):
                return value

    # Match metric descriptions for columns referenced by metric expressions.
    for metric in (semantic.get("metrics") or {}).values():
        if not isinstance(metric, dict):
            continue
        if metric.get("table") != table:
            continue
        expression = str(metric.get("sql_expression", ""))
        if re.search(rf"\b{re.escape(column)}\b", expression):
            return str(metric.get("description") or "")
    return ""


def _semantic_fks(semantic: dict[str, Any]) -> list[dict[str, str]]:
    found: set[tuple[str, str, str, str]] = set()
    for metric in (semantic.get("metrics") or {}).values():
        if not isinstance(metric, dict):
            continue
        for join in metric.get("joins") or []:
            if not isinstance(join, dict):
                continue
            condition = str(join.get("condition") or "")
            m = _EQ.fullmatch(condition.strip())
            if not m:
                continue
            left_table, left_col, right_table, right_col = m.groups()
            fact_table = str(metric.get("table") or "")
            # Prefer the dimension -> fact relationship implied by a metric join.
            if left_table == fact_table:
                src_t, src_c, dst_t, dst_c = left_table, left_col, right_table, right_col
            elif right_table == fact_table:
                src_t, src_c, dst_t, dst_c = right_table, right_col, left_table, left_col
            else:
                src_t, src_c, dst_t, dst_c = left_table, left_col, right_table, right_col
            found.add((src_t, src_c, dst_t, dst_c))
    return [
        {"from_table": a, "from_column": b, "to_table": c, "to_column": d}
        for a, b, c, d in sorted(found)
    ]


def _sqlite_schema(db_path: Path, allow_real_samples: bool) -> tuple[list[str], dict[str, list[dict[str, Any]]], list[dict[str, str]]]:
    conn = sqlite3.connect(db_path)
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        columns: dict[str, list[dict[str, Any]]] = {}
        fks: list[dict[str, str]] = []
        for table in tables:
            rows = conn.execute(f"PRAGMA table_info({_qident(table)})").fetchall()
            cols = []
            for cid, name, ctype, notnull, dflt, pk in rows:
                samples: list[str] = []
                if allow_real_samples and name in SAMPLE_ALLOWLIST.get(table, []):
                    samples = [str(r[0]) for r in conn.execute(
                        f"SELECT DISTINCT {_qident(name)} FROM {_qident(table)} WHERE {_qident(name)} IS NOT NULL LIMIT 5"
                    ).fetchall()]
                elif name in SYNTHETIC.get(table, {}):
                    samples = list(SYNTHETIC[table][name])
                cols.append({"name": name, "type": ctype or "UNKNOWN", "pk": bool(pk), "sample_values": samples})
            columns[table] = cols
            for row in conn.execute(f"PRAGMA foreign_key_list({_qident(table)})").fetchall():
                # SQLite columns: id, seq, table, from, to, on_update, on_delete, match, ...
                fks.append({
                    "from_table": table,
                    "from_column": row[3],
                    "to_table": row[2],
                    "to_column": row[4],
                })
        return tables, columns, fks
    finally:
        conn.close()


def _duckdb_schema(db_path: Path, allow_real_samples: bool) -> tuple[list[str], dict[str, list[dict[str, Any]]], list[dict[str, str]]]:
    try:
        import duckdb  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("DuckDB compilation requires the 'duckdb' package") from exc

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema NOT IN ('information_schema', 'pg_catalog') "
                "AND table_type = 'BASE TABLE' ORDER BY table_name"
            ).fetchall()
        ]
        columns: dict[str, list[dict[str, Any]]] = {}
        for table in tables:
            rows = conn.execute(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = ? ORDER BY ordinal_position",
                [table],
            ).fetchall()
            cols: list[dict[str, Any]] = []
            for name, dtype in rows:
                samples: list[str] = []
                if allow_real_samples and name in SAMPLE_ALLOWLIST.get(table, []):
                    samples = [str(r[0]) for r in conn.execute(
                        f"SELECT DISTINCT {_qident(name)} FROM {_qident(table)} WHERE {_qident(name)} IS NOT NULL LIMIT 5"
                    ).fetchall()]
                elif name in SYNTHETIC.get(table, {}):
                    samples = list(SYNTHETIC[table][name])
                cols.append({"name": name, "type": str(dtype or "UNKNOWN"), "pk": False, "sample_values": samples})
            columns[table] = cols
        # DuckDB physical FK support varies by version; semantic joins are merged later.
        return tables, columns, []
    finally:
        conn.close()


def compile_mschema(db_path: str, output_path: str, semantic_path: str = "src/config/semantic_layer.yaml", descriptions_path: str = "docs/table_descriptions.yaml", allow_real_samples: bool = False) -> dict[str, Any]:
    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"Database not found: {db}")

    semantic = _load_semantic(Path(semantic_path))
    descriptions = _load_semantic(Path(descriptions_path))
    suffix = db.suffix.lower()
    if suffix in {".duckdb", ".ddb"}:
        tables, physical_columns, physical_fks = _duckdb_schema(db, allow_real_samples)
    elif suffix in {".db", ".sqlite", ".sqlite3"}:
        tables, physical_columns, physical_fks = _sqlite_schema(db, allow_real_samples)
    else:
        raise ValueError(f"Unsupported database type: {suffix or 'none'}; use DuckDB or SQLite")

    semantic_tables = semantic.get("tables") or {}
    mschema: dict[str, Any] = {
        "schema_version": "1.0",
        "db_id": db.stem,
        "source": {"path": str(db), "real_samples_enabled": bool(allow_real_samples)},
        "tables": {},
        "foreign_keys": [],
    }

    for table in tables:
        cols = []
        table_desc = ""
        if isinstance(semantic_tables.get(table), dict):
            table_desc = str(semantic_tables[table].get("description") or "")
        if not table_desc and isinstance(descriptions.get(table), dict):
            table_desc = str(descriptions[table].get("description") or "")
        if not table_desc:
            table_desc = f"Table {table}"

        for col in physical_columns.get(table, []):
            desc = _semantic_descriptions(semantic, table, col["name"])
            if not desc and isinstance(descriptions.get(table), dict):
                for doc_col in descriptions[table].get("columns", []) or []:
                    if isinstance(doc_col, dict) and doc_col.get("name") == col["name"]:
                        desc = str(doc_col.get("description") or "")
                        break
            desc = desc or col["name"].replace("_", " ").title()
            cols.append({
                "name": col["name"],
                "type": col["type"],
                "description": desc,
                "pk": "PK" if col.get("pk") else "",
                "sample_values": col.get("sample_values", []),
            })

        mschema["tables"][table] = {"description": table_desc, "columns": cols}

    fk_keys = {(x["from_table"], x["from_column"], x["to_table"], x["to_column"]) for x in physical_fks}
    for item in _semantic_fks(semantic):
        key = (item["from_table"], item["from_column"], item["to_table"], item["to_column"])
        if key not in fk_keys:
            physical_fks.append(item)
            fk_keys.add(key)
    mschema["foreign_keys"] = sorted(physical_fks, key=lambda x: (x["from_table"], x["from_column"], x["to_table"], x["to_column"]))

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        yaml.safe_dump(mschema, f, allow_unicode=True, sort_keys=False)
    print(f"✓ {out} created")
    print(f"  Tables: {len(mschema['tables'])}, FKs: {len(mschema['foreign_keys'])}")
    return mschema


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile M-Schema from DuckDB/SQLite plus the ITXN semantic layer")
    parser.add_argument("--db", default="data/bank.duckdb")
    parser.add_argument("--output", default="src/config/mschema.yaml")
    parser.add_argument("--semantic", default="src/config/semantic_layer.yaml")
    parser.add_argument("--descriptions", default="docs/table_descriptions.yaml")
    parser.add_argument("--allow-real-samples", action="store_true", help="Copy allow-listed real sample values")
    args = parser.parse_args()
    compile_mschema(args.db, args.output, args.semantic, args.descriptions, args.allow_real_samples)


if __name__ == "__main__":
    main()
