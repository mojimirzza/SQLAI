import json
from pathlib import Path

import yaml

from core.models import Intent
from ports.vector_store_port import VectorStorePort


class ContextBuilder:
    """Build deterministic LLM context from authoritative schema + optional M-Schema artifact.

    The two-argument constructor remains backward compatible. M-Schema is an
    optional enrichment layer and is loaded once at application startup.
    """

    def __init__(self, vector_store: VectorStorePort, schema_path: str, mschema_path: str | None = None):
        self.vector_store = vector_store
        with open(schema_path, encoding="utf-8") as f:
            self.table_descriptions = yaml.safe_load(f) or {}
        self.mschema = {}
        self.mschema_path = mschema_path
        if mschema_path:
            try:
                with open(mschema_path, encoding="utf-8") as f:
                    self.mschema = yaml.safe_load(f) or {}
            except (OSError, yaml.YAMLError):
                self.mschema = {}

    def _format_mschema(self, table_name: str) -> str:
        table = self.mschema.get("tables", {}).get(table_name)
        if not table:
            return ""
        lines = [f"# Table: {table_name}", f"# Description: {table.get('description', '')}", "["]
        for col in table.get("columns", []):
            pk = ', "PK"' if col.get("pk") else ', ""'
            samples = json.dumps(col.get("sample_values") or [], ensure_ascii=False)
            lines.append(
                f'  ("{col["name"]}", "{col.get("type", "UNKNOWN")}", '
                f'"{col.get("description", "")}"{pk}, {samples}),'
            )
        lines.append("]")
        return "\n".join(lines)

    def _fk_lines(self, requested_tables: set[str]) -> str:
        fks = self.mschema.get("foreign_keys", [])
        if not fks:
            return ""
        lines = ["【Foreign Keys】"]
        for fk in fks:
            if fk.get("from_table") in requested_tables or fk.get("to_table") in requested_tables:
                lines.append(
                    f"  {fk['from_table']}.{fk['from_column']} → "
                    f"{fk['to_table']}.{fk['to_column']}"
                )
        return "\n".join(lines) if len(lines) > 1 else ""

    def build(self, intent: Intent) -> dict:
        context = {"tables": [], "business_context": [], "mschema": ""}
        requested = intent.relevant_tables if intent.relevant_tables is not None else list(self.table_descriptions)

        parts = []
        requested_set = set(requested[:5])
        for table_name in requested[:5]:
            if table_name in self.table_descriptions:
                context["tables"].append({
                    "name": table_name,
                    **self.table_descriptions[table_name],
                })
            ms = self._format_mschema(table_name)
            if ms:
                parts.append(ms)

        if parts:
            context["mschema"] = "【Schema】\n" + "\n".join(parts)
            fk = self._fk_lines(requested_set)
            if fk:
                context["mschema"] += "\n" + fk

        if intent.needs_business_context:
            docs = self.vector_store.search(intent.category, top_k=3)
            context["business_context"] = [d.content for d in docs]

        return context
