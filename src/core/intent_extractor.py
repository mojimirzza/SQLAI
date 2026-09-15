import json
from core.models import UserQuery, Intent
from ports.llm_port import LLMPort

INTENT_SYSTEM_PROMPT = """You are the intent/planning layer of a banking Text-to-SQL system.
Your job is NOT to write SQL. Return only structured intent data.

Extract:
- category: the closest supported business metric/intent; keep existing metric names for aggregate queries
- query_type: one of aggregate, detail, top_n_detail, top_n_aggregate
- confidence: 0..1
- entities: dimensions, detail_view, detail_fields, time_range, start_date, end_date,
  order_by, limit when explicitly requested
- needs_business_context: true only when business definitions are needed
- relevant_tables: only tables supported by the supplied schema
- needs_clarification: true when the request is materially ambiguous or unsupported

Rules:
1. Never invent a table, column, metric, date, or business definition.
2. Preserve the user's requested aggregation, query shape, and dimensions.
3. DETAIL means individual fact records; TOP_N_DETAIL means individual records ordered by a selected field;
   TOP_N_AGGREGATE means grouped entities ordered by an aggregate metric.
4. For detail queries, use only detail fields supported by the supplied semantic layer; never invent customer/entity fields.
5. Do not put SQL, SQL expressions, or raw ORDER BY clauses into entities.
6. If a relative date is requested, normalize it to a clear time_range label
   (today, yesterday, this_week, this_month, last_month, etc.); the deterministic
   SQL layer will interpret it.
7. If confidence is below 0.70, ask one concise clarification question.
"""

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "query_type": {"type": "string", "enum": ["aggregate", "detail", "top_n_detail", "top_n_aggregate"]},
        "confidence": {"type": "number"},
        "entities": {"type": "object"},
        "needs_clarification": {"type": "boolean"},
        "clarification_question": {"type": "string"},
        "needs_business_context": {"type": "boolean"},
        "relevant_tables": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["category", "query_type", "confidence", "entities", "needs_clarification"],
}


class IntentExtractor:
    def __init__(self, llm: LLMPort, confidence_threshold: float = 0.70, mschema_path: str | None = None, semantic_layer_path: str | None = None):
        self.llm = llm
        self.confidence_threshold = confidence_threshold
        self.mschema = {}
        self.mschema_context = ""
        self.semantic_layer = {}
        self.semantic_context = ""
        if mschema_path:
            try:
                import yaml
                with open(mschema_path, encoding="utf-8") as f:
                    self.mschema = yaml.safe_load(f) or {}
                self.mschema_context = self._format_mschema()
            except (OSError, ValueError):
                self.mschema = {}
                self.mschema_context = ""
        if semantic_layer_path:
            try:
                import yaml
                with open(semantic_layer_path, encoding="utf-8") as f:
                    self.semantic_layer = yaml.safe_load(f) or {}
                self.semantic_context = self._format_semantic_layer()
            except (OSError, ValueError):
                self.semantic_layer = {}
                self.semantic_context = ""

    def _format_semantic_layer(self) -> str:
        lines = ["【Semantic Layer】"]
        metrics = self.semantic_layer.get("metrics", {})
        if metrics:
            lines.append("Supported aggregate metrics: " + ", ".join(metrics.keys()))
        views = self.semantic_layer.get("detail_views", {})
        for view_name, view in views.items():
            lines.append(f"Detail view: {view_name} (max_limit={view.get('max_limit', 100)})")
            fields = view.get("fields", {})
            if fields:
                lines.append("  fields: " + ", ".join(fields.keys()))
        return "\n".join(lines)

    def _format_mschema(self) -> str:
        parts = []
        tables = self.mschema.get("tables", {})
        for table_name, table in list(tables.items())[:8]:
            lines = [f"# Table: {table_name}", f"# Description: {table.get('description', '')}", "["]
            for col in table.get("columns", []):
                pk = ', "PK"' if col.get("pk") else ', ""'
                samples = json.dumps(col.get("sample_values") or [], ensure_ascii=False)
                lines.append(f'  ("{col["name"]}", "{col.get("type", "UNKNOWN")}", "{col.get("description", "")}"{pk}, {samples}),')
            lines.append("]")
            parts.append("\n".join(lines))
        fks = self.mschema.get("foreign_keys", [])
        if fks:
            parts.append("【Foreign Keys】\n" + "\n".join(
                f"  {fk['from_table']}.{fk['from_column']} → {fk['to_table']}.{fk['to_column']}" for fk in fks
            ))
        return "【M-Schema】\n" + "\n".join(parts) if parts else ""

    def extract(self, query: UserQuery) -> Intent:
        prompt = f"User query: {query.text}\nUser role: {query.user_role}"
        if self.semantic_context:
            prompt += f"\n\n{self.semantic_context}"
        if self.mschema_context:
            prompt += f"\n\n{self.mschema_context}"
        result = self.llm.generate(prompt, INTENT_SYSTEM_PROMPT, schema=INTENT_SCHEMA)
        needs = result.needs_clarification or result.confidence < self.confidence_threshold
        return Intent(
            category=result.intent,
            confidence=max(0.0, min(1.0, result.confidence)),
            entities=result.entities or {},
            needs_clarification=needs,
            clarification_question=result.clarification_question,
            needs_business_context=bool(result.needs_business_context),
            relevant_tables=list(result.relevant_tables or []),
            query_type=getattr(result, "query_type", None) or (getattr(result, "data", {}) or {}).get("query_type") or (result.entities or {}).get("query_type", "aggregate"),
        )
