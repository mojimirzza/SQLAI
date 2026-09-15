from datetime import date, timedelta
import math
import re

from jinja2 import Environment, BaseLoader, StrictUndefined

from core.models import Intent, GeneratedSQL, JoinSpec
from ports.semantic_layer_port import SemanticLayerPort

AGGREGATE_SQL_TEMPLATE = """SELECT
    {%- for dim in resolved_dimensions %}
    {{ dim.sql_ref }} AS {{ dim.alias }}{% if not loop.last %}, {% endif %}
    {%- endfor %}
    {%- if resolved_dimensions %}, {% endif %}
    {{ metric.sql_expression }} AS {{ metric.name }}
FROM {{ metric.table }}
{%- for join in joins %}
{{ join.type }} JOIN {{ join.table }} ON {{ join.on }}
{%- endfor %}
{%- if filters %}
WHERE {{ filters | join(' AND ') }}
{%- endif %}
{%- if resolved_dimensions %}
GROUP BY {{ group_by | join(', ') }}
{%- endif %}
{%- if order_by %}
ORDER BY {{ order_by }}
{%- endif %}
{%- if limit %}
LIMIT {{ limit }}
{%- endif %}"""

DETAIL_SQL_TEMPLATE = """SELECT
    {%- for field in fields %}
    {{ field.sql_expression }} AS {{ field.alias }}{% if not loop.last %}, {% endif %}
    {%- endfor %}
FROM {{ detail_view.table }}
{%- for join in joins %}
{{ join.type }} JOIN {{ join.table }} ON {{ join.on }}
{%- endfor %}
{%- if filters %}
WHERE {{ filters | join(' AND ') }}
{%- endif %}
{%- if order_by %}
ORDER BY {{ order_by }}
{%- endif %}
LIMIT {{ limit }}"""

# Backward-compatible dimension map for aggregate queries. Detail fields are
# resolved from the semantic layer detail view instead of this hard-coded map.
DIMENSION_MAP = {
    # dim_date
    "year": ("dim_date", "year", "dim_date"),
    "quarter": ("dim_date", "quarter", "dim_date"),
    "month": ("dim_date", "month", "dim_date"),
    "month_name": ("dim_date", "month_name", "dim_date"),
    "day_of_month": ("dim_date", "day_of_month", "dim_date"),
    "day_of_week": ("dim_date", "day_of_week", "dim_date"),
    "day_name": ("dim_date", "day_name", "dim_date"),
    "week_of_year": ("dim_date", "week_of_year", "dim_date"),
    "is_weekend": ("dim_date", "is_weekend", "dim_date"),
    "is_holiday": ("dim_date", "is_holiday", "dim_date"),
    # dim_time
    "hour24": ("dim_time", "hour24", "dim_time"),
    "hour12": ("dim_time", "hour12", "dim_time"),
    "am_pm": ("dim_time", "am_pm", "dim_time"),
    "time_of_day": ("dim_time", "time_of_day", "dim_time"),
    # dim_server
    "server_name": ("dim_server", "server_name", "dim_server"),
    "server_type": ("dim_server", "server_type", "dim_server"),
    "location": ("dim_server", "location", "dim_server"),
    # dim_terminal
    "device_category": ("dim_terminal", "device_category", "dim_terminal"),
    "entry_mode_desc": ("dim_terminal", "entry_mode_desc", "dim_terminal"),
    "terminal_risk_score": ("dim_terminal", "terminal_risk_score", "dim_terminal"),
    # dim_status
    "status_code": ("dim_status", "status_code", "dim_status"),
    "lifecycle_stage": ("dim_status", "lifecycle_stage", "dim_status"),
    # dim_error
    "err_severity": ("dim_error", "err_severity", "dim_error"),
    "error_description": ("dim_error", "error_description", "dim_error"),
    # fact_transaction raw SKs
    "date_in_sk": ("fact_transaction", "date_in_sk", None),
    "time_in_sk": ("fact_transaction", "time_in_sk", None),
    "server_sk": ("fact_transaction", "server_sk", None),
    "terminal_sk": ("fact_transaction", "terminal_sk", None),
    "status_sk": ("fact_transaction", "status_sk", None),
    "error_sk": ("fact_transaction", "error_sk", None),
}

TIME_OF_DAY_RANGES = {
    "morning": (5, 11),
    "afternoon": (12, 16),
    "evening": (17, 20),
    "night": (21, 4),
}


class SQLGenerator:
    """Deterministic SQL generation from the semantic layer; the LLM never writes SQL."""

    CATEGORY_TO_METRIC = {
        "total_transactions": "total_transactions",
        "total_amount": "total_amount",
        "approval_rate": "approval_rate",
        "avg_switch_latency": "avg_switch_latency",
        "stuck_transactions": "stuck_transactions",
        "hot_card_count": "hot_card_count",
        "error_count": "error_count",
    }
    AGGREGATE_CATEGORIES = set(CATEGORY_TO_METRIC)
    SUPPORTED_QUERY_TYPES = {"aggregate", "detail", "top_n_detail", "top_n_aggregate"}

    def __init__(self, semantic_layer: SemanticLayerPort):
        self.semantic_layer = semantic_layer
        self.env = Environment(loader=BaseLoader(), undefined=StrictUndefined)
        self.aggregate_template = self.env.from_string(AGGREGATE_SQL_TEMPLATE)
        self.detail_template = self.env.from_string(DETAIL_SQL_TEMPLATE)

    def generate(self, intent: Intent, context: dict | None = None, reference_date=None) -> GeneratedSQL:
        context = context or {}
        if reference_date is None:
            reference_date = context.get("reference_date")
        query_type = self._query_type(intent)
        if query_type not in self.SUPPORTED_QUERY_TYPES:
            raise ValueError(f"Unsupported query type: {query_type}")
        if query_type in {"detail", "top_n_detail"}:
            return self._generate_detail(intent, context, query_type, reference_date=reference_date)
        return self._generate_aggregate(intent, context, query_type, reference_date=reference_date)

    def _query_type(self, intent: Intent) -> str:
        explicit = getattr(intent, "query_type", None) or (intent.entities or {}).get("query_type")
        if explicit:
            return str(explicit).strip().lower()
        category = str(intent.category).strip().lower()
        if category in {"detail", "transaction_detail"}:
            return "detail"
        if category in {"detail_top_n", "top_n_detail"}:
            return "top_n_detail"
        if category in {"top_n_aggregate", "aggregate_top_n"}:
            return "top_n_aggregate"
        return "aggregate"

    def _generate_aggregate(self, intent: Intent, context: dict, query_type: str, reference_date=None) -> GeneratedSQL:
        category = intent.category
        metric_name = self.CATEGORY_TO_METRIC.get(category, category)
        metric = self.semantic_layer.get_metric(metric_name)
        if not metric:
            raise ValueError(f"Unsupported metric/intent: {intent.category}")

        resolved_dims, needed_joins = self._resolve_dimensions(intent, metric)
        filters = list(metric.filters)
        filters.extend(self._build_filters(intent, metric, resolved_dims, reference_date=reference_date))
        needed_joins.extend(self._resolve_filter_joins(intent, metric, existing_joins=needed_joins))
        order_by = self._safe_aggregate_order_by(intent, metric, resolved_dims)
        limit = self._safe_limit(intent.entities.get("limit"))
        if query_type == "top_n_aggregate":
            if limit is None:
                raise ValueError("TOP_N_AGGREGATE requires an explicit positive limit")
            if not order_by:
                raise ValueError("TOP_N_AGGREGATE requires a semantic order_by field")

        deduped_joins = self._dedupe_joins(needed_joins)
        group_by = [d["sql_ref"] for d in resolved_dims]
        sql = self.aggregate_template.render(
            metric=metric,
            resolved_dimensions=resolved_dims,
            joins=deduped_joins,
            filters=filters,
            group_by=group_by,
            order_by=order_by,
            limit=limit,
        ).strip()
        return GeneratedSQL(
            sql,
            metric.name,
            [d["alias"] for d in resolved_dims],
            filters,
            deduped_joins,
        )

    def _generate_detail(self, intent: Intent, context: dict, query_type: str, reference_date=None) -> GeneratedSQL:
        entities = intent.entities or {}
        view_name = str(entities.get("detail_view") or "transaction")
        view = self.semantic_layer.get_detail_view(view_name)
        if not view:
            raise ValueError(f"Unsupported detail view: {view_name}")

        requested = entities.get("detail_fields", entities.get("fields"))
        if requested is None:
            requested = list(view.default_fields)
        if isinstance(requested, str):
            requested = [requested]
        if not isinstance(requested, list) or not requested:
            raise ValueError("Detail query requires at least one semantic detail field")
        if len(requested) > 30:
            raise ValueError("Detail query requests too many fields")

        fields = []
        for name in requested:
            if not isinstance(name, str) or name not in view.fields:
                raise ValueError(f"Unsupported detail field: {name}")
            fields.append(view.fields[name])

        filters = self._build_filters_for_detail(intent, reference_date=reference_date)
        limit = self._safe_limit(entities.get("limit"), maximum=min(1000, max(1, int(view.max_limit))))
        if limit is None:
            raise ValueError(f"{query_type.upper()} requires an explicit positive limit")

        order_by = self._safe_detail_order_by(intent, view)
        if query_type == "top_n_detail" and not order_by:
            raise ValueError("TOP_N_DETAIL requires a semantic order_by field")

        # Only join semantic tables required by the selected projection or
        # filters. The candidate graph still comes exclusively from the
        # semantic layer; callers can never supply arbitrary JOIN clauses.
        joins = self._resolve_detail_joins(view, fields, intent)
        sql = self.detail_template.render(
            fields=fields,
            detail_view=view,
            joins=joins,
            filters=filters,
            order_by=order_by,
            limit=limit,
        ).strip()
        return GeneratedSQL(
            sql,
            f"detail_view:{view.name}",
            [field.alias for field in fields],
            filters,
            joins,
        )

    def _resolve_detail_joins(self, view, fields, intent):
        """Select only approved joins required by fields and filter entities."""
        required = set()
        for field in fields:
            required.update(re.findall(r"\b(dim_[A-Za-z0-9_]+)\.", field.sql_expression))

        entities = intent.entities or {}
        required.update(self._required_filter_tables(entities))
        available = {j["table"]: j for j in (view.joins or [])}
        joins = []
        for table in sorted(required):
            join = available.get(table)
            if not join:
                join = getattr(self.semantic_layer, "get_join", lambda _t: None)(table)
            if not join:
                raise ValueError(f"Semantic layer has no approved join for detail table: {table}")
            joins.append(JoinSpec(join["table"], join["condition"], join["type"]))
        return self._dedupe_joins(joins)

    @staticmethod
    def _required_filter_tables(entities):
        required = set()
        if any(entities.get(k) is not None for k in ("server_name", "server_type")):
            required.add("dim_server")
        if any(entities.get(k) is not None for k in ("device_category", "entry_mode_desc", "terminal_risk_score")):
            required.add("dim_terminal")
        if any(entities.get(k) is not None for k in ("status_code", "lifecycle_stage")):
            required.add("dim_status")
        if any(entities.get(k) is not None for k in ("err_severity", "error_severity")):
            required.add("dim_error")
        if entities.get("time_of_day") is not None or entities.get("hour24") is not None:
            required.add("dim_time")
        if any(entities.get(k) is not None for k in ("date_range", "start_date", "end_date", "is_weekend", "is_holiday")):
            required.add("dim_date")
        return required

    @staticmethod
    def _dedupe_joins(joins):
        seen = set()
        out = []
        for j in joins:
            if j.table not in seen:
                seen.add(j.table)
                out.append(j)
        return out

    def _get_semantic_join(self, table, metric=None):
        """Return an allow-listed join declaration from the semantic layer."""
        if metric:
            for join in metric.joins or []:
                if join.get("table") == table:
                    return JoinSpec(join["table"], join["condition"], join["type"])
        getter = getattr(self.semantic_layer, "get_join", None)
        if callable(getter):
            join = getter(table)
            if join:
                if isinstance(join, JoinSpec):
                    return join
                return JoinSpec(join["table"], join["condition"], join["type"])
        return None

    def _resolve_dimensions(self, intent, metric):
        requested = intent.entities.get("dimensions", [])
        if isinstance(requested, str):
            requested = [requested]

        resolved = []
        needed_joins = []
        metric_joins = {j["table"]: j for j in (metric.joins or [])}

        for dim in requested:
            if dim not in DIMENSION_MAP:
                raise ValueError(f"Unsupported dimension: {dim}")
            table_alias, col_name, join_table = DIMENSION_MAP[dim]
            sql_ref = f"{table_alias}.{col_name}"
            alias = f"{table_alias}_{col_name}"
            resolved.append({"sql_ref": sql_ref, "alias": alias, "dim": dim})
            if join_table:
                join = self._get_semantic_join(join_table, metric)
                if join:
                    needed_joins.append(join)
        return resolved, needed_joins

    def _resolve_filter_joins(self, intent, metric, existing_joins=None):
        """Resolve all joins required by allow-listed filter entities."""
        required = self._required_filter_tables(intent.entities or {})
        joins = []
        existing = {j.table if isinstance(j, JoinSpec) else j.get("table") for j in (existing_joins or [])}
        for table in sorted(required):
            if table in existing:
                continue
            join = self._get_semantic_join(table, metric)
            if join:
                joins.append(join)
            else:
                raise ValueError(f"Semantic layer has no approved join for filter table: {table}")
        return joins

    def _build_filters(self, intent, metric, resolved_dims, reference_date=None):
        """Build allow-listed aggregate filters from intent entities.

        Scalar values preserve the historical ``column = literal`` contract.
        List/tuple values are rendered as ``column IN (literal, ...)`` so an
        intent extractor cannot accidentally turn a Python collection into
        one quoted string such as ``['Primary', 'Backup']``.
        """
        return self._build_filters_common(intent, reference_date=reference_date)

    def _build_filters_for_detail(self, intent, reference_date=None):
        """Build the same safe filter contract for detail/Top-N queries."""
        return self._build_filters_common(intent, reference_date=reference_date)

    def _build_filters_common(self, intent, reference_date=None):
        e = intent.entities or {}
        filters = []

        specs = [
            ("server_name", "dim_server.server_name", "string"),
            ("server_type", "dim_server.server_type", "string"),
            ("device_category", "dim_terminal.device_category", "string"),
            ("entry_mode_desc", "dim_terminal.entry_mode_desc", "string"),
            ("status_code", "dim_status.status_code", "integer"),
            ("lifecycle_stage", "dim_status.lifecycle_stage", "string"),
            ("error_severity", "dim_error.err_severity", "integer"),
            ("err_severity", "dim_error.err_severity", "integer"),
        ]
        for key, column, kind in specs:
            if e.get(key) is not None:
                filters.append(self._build_entity_filter(e[key], column, kind, semantic_key=key))

        boolean_specs = [
            ("is_approved", "fact_transaction.is_approved"),
            ("has_error", "fact_transaction.has_error"),
            ("is_stuck", "fact_transaction.is_stuck"),
            ("is_hot_card", "fact_transaction.is_hot_card"),
            ("is_weekend", "dim_date.is_weekend"),
            ("is_holiday", "dim_date.is_holiday"),
        ]
        for key, column in boolean_specs:
            if e.get(key) is not None:
                filters.append(self._build_boolean_filter(e[key], column))

        if e.get("min_amount") is not None:
            filters.append(self._build_number_comparison(e["min_amount"], "fact_transaction.txnamt", ">="))
        if e.get("max_amount") is not None:
            filters.append(self._build_number_comparison(e["max_amount"], "fact_transaction.txnamt", "<="))

        tod = e.get("time_of_day")
        if tod is not None:
            if not isinstance(tod, str):
                raise ValueError("time_of_day must be a string")
            tod = tod.lower()
            if tod not in TIME_OF_DAY_RANGES:
                raise ValueError(f"Unsupported time_of_day: {tod}")
            filters.extend(self._time_of_day_filter(tod))

        if e.get("hour24") is not None:
            hour_value = e["hour24"]
            if isinstance(hour_value, dict):
                filters.append(self._build_range_filter(hour_value, "dim_time.hour24", "integer", 0, 23))
            else:
                h = self._validated_integer(hour_value, "hour24")
                if not 0 <= h <= 23:
                    raise ValueError("hour24 must be between 0 and 23")
                filters.append(f"dim_time.hour24 = {h}")

        date_range = e.get("date_range")
        if date_range is not None:
            filters.append(self._build_date_range_filter(date_range))
        elif e.get("start_date") is not None or e.get("end_date") is not None:
            start_sk, end_sk = self._date_sk_bounds(
                None, e.get("start_date"), e.get("end_date"), reference_date=reference_date
            )
            if start_sk is not None and end_sk is not None:
                filters.append(
                    f"fact_transaction.date_in_sk >= {start_sk} AND fact_transaction.date_in_sk < {end_sk}"
                )
        else:
            start_sk, end_sk = self._date_sk_bounds(
                e.get("time_range"), reference_date=reference_date
            )
            if start_sk is not None and end_sk is not None:
                filters.append(
                    f"fact_transaction.date_in_sk >= {start_sk} AND fact_transaction.date_in_sk < {end_sk}"
                )
        return filters

    def _build_entity_filter(self, value, column, kind, semantic_key=None):
        """Render one semantic entity filter, preserving scalar compatibility.

        ``list`` and ``tuple`` are treated as a value collection and therefore
        become ``IN (...)``. Every member is validated and serialized as a SQL
        literal; unsupported/empty collections fail closed rather than emitting
        invalid or unsafe SQL.
        """
        is_collection = isinstance(value, (list, tuple))
        values = list(value) if is_collection else [value]
        if not values:
            raise ValueError(f"Empty filter list is not allowed for {column}")

        literals = [self._entity_literal(self._canonicalize_string(semantic_key, item), kind) for item in values]
        if is_collection:
            return f"{column} IN ({', '.join(literals)})"
        return f"{column} = {literals[0]}"

    def _canonicalize_string(self, semantic_key, value):
        if semantic_key is None or not isinstance(value, str):
            return value
        getter = getattr(self.semantic_layer, "get_canonical_value", None)
        if callable(getter):
            return getter(semantic_key, value)
        return value

    def _entity_literal(self, value, kind):
        """Convert an allow-listed entity value into a SQL literal."""
        if kind == "string":
            if not isinstance(value, str):
                raise ValueError(f"Expected string filter value, got {type(value).__name__}")
            return f"'{self._quote(value)}'"

        if kind == "integer":
            if isinstance(value, bool):
                raise ValueError("Boolean is not a valid integer filter value")
            try:
                return str(int(value))
            except (TypeError, ValueError, OverflowError):
                raise ValueError(f"Invalid integer filter value: {value!r}") from None

        if kind == "number":
            if isinstance(value, bool):
                raise ValueError("Boolean is not a valid numeric filter value")
            if not isinstance(value, (int, float)):
                raise ValueError(f"Invalid numeric filter value: {value!r}")
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"Invalid numeric filter value: {value!r}")
            return str(value)

        raise ValueError(f"Unsupported entity filter kind: {kind}")

    @staticmethod
    def _time_of_day_filter(tod):
        if tod == "night":
            return ["(dim_time.hour24 >= 21 OR dim_time.hour24 <= 4)"]
        start_h, end_h = TIME_OF_DAY_RANGES[tod]
        return [f"dim_time.hour24 >= {start_h} AND dim_time.hour24 <= {end_h}"]

    @staticmethod
    def _validated_integer(value, field_name):
        if isinstance(value, bool):
            raise ValueError(f"{field_name} must be an integer")
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"Invalid integer value for {field_name}: {value!r}") from None

    def _build_boolean_filter(self, value, column):
        if isinstance(value, (list, tuple)):
            values = list(value)
            if not values:
                raise ValueError(f"Empty boolean filter list is not allowed for {column}")
            ints = []
            for item in values:
                if not isinstance(item, bool):
                    raise ValueError(f"Boolean filter requires True/False for {column}")
                ints.append("1" if item else "0")
            return f"{column} IN ({', '.join(ints)})"
        if not isinstance(value, bool):
            raise ValueError(f"Boolean filter requires True/False for {column}")
        return f"{column} = {1 if value else 0}"

    def _build_number_comparison(self, value, column, operator):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Numeric filter requires int/float for {column}")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"Invalid numeric filter value for {column}: {value!r}")
        return f"{column} {operator} {value}"

    def _build_range_filter(self, value, column, kind, minimum=None, maximum=None):
        if not isinstance(value, dict):
            raise ValueError(f"Range filter for {column} must be an object")
        lower = value.get("from")
        upper = value.get("to")
        if lower is None and upper is None:
            raise ValueError(f"Range filter for {column} requires from/to")
        clauses = []
        if lower is not None:
            literal = self._entity_literal(lower, kind)
            if minimum is not None and int(lower) < minimum:
                raise ValueError(f"{column} range lower bound out of range")
            clauses.append(f"{column} >= {literal}")
        if upper is not None:
            literal = self._entity_literal(upper, kind)
            if maximum is not None and int(upper) > maximum:
                raise ValueError(f"{column} range upper bound out of range")
            clauses.append(f"{column} <= {literal}")
        if lower is not None and upper is not None and int(lower) > int(upper):
            raise ValueError(f"{column} range from exceeds to")
        return " AND ".join(clauses)

    def _build_date_range_filter(self, value):
        if not isinstance(value, dict):
            raise ValueError("date_range must be an object with from/to")
        lower = value.get("from")
        upper = value.get("to")
        if lower is None and upper is None:
            raise ValueError("date_range requires from or to")
        clauses = []
        parsed = {}
        for label, raw in (("from", lower), ("to", upper)):
            if raw is None:
                continue
            try:
                parsed[label] = date.fromisoformat(str(raw).replace("/", "-"))
            except (ValueError, TypeError):
                raise ValueError(f"Invalid date_range {label}: {raw!r}") from None
        if lower is not None:
            clauses.append(f"dim_date.full_date >= '{parsed['from'].isoformat()}'")
        if upper is not None:
            clauses.append(f"dim_date.full_date <= '{parsed['to'].isoformat()}'")
        if lower is not None and upper is not None and parsed["from"] > parsed["to"]:
            raise ValueError("date_range from exceeds to")
        return " AND ".join(clauses)

    @staticmethod
    def _date_sk_bounds(time_range, start_date=None, end_date=None, reference_date=None):
        if start_date is not None or end_date is not None:
            try:
                if start_date is None or end_date is None:
                    raise ValueError("both start_date and end_date are required")
                s_date = date.fromisoformat(str(start_date).replace("/", "-"))
                e_date = date.fromisoformat(str(end_date).replace("/", "-"))
                if e_date < s_date:
                    raise ValueError("end_date precedes start_date")
                return int(s_date.strftime("%Y%m%d")), int((e_date + timedelta(days=1)).strftime("%Y%m%d"))
            except (ValueError, TypeError):
                return None, None
        if not time_range:
            return None, None
        try:
            today = reference_date
            if today is None:
                today = date.today()
            elif not isinstance(today, date):
                today = date.fromisoformat(str(today).replace("/", "-"))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid reference_date: {reference_date!r}") from None

        tr = str(time_range).lower()
        if tr == "today":
            return int(today.strftime("%Y%m%d")), int((today + timedelta(days=1)).strftime("%Y%m%d"))
        if tr == "yesterday":
            d = today - timedelta(days=1)
            return int(d.strftime("%Y%m%d")), int(today.strftime("%Y%m%d"))
        if tr == "this_month":
            start = today.replace(day=1)
            nxt = date(today.year + (today.month == 12), 1 if today.month == 12 else today.month + 1, 1)
            return int(start.strftime("%Y%m%d")), int(nxt.strftime("%Y%m%d"))
        if tr == "this_week":
            start = today - timedelta(days=today.weekday())
            return int(start.strftime("%Y%m%d")), int((start + timedelta(days=7)).strftime("%Y%m%d"))
        if tr == "last_week":
            end = today - timedelta(days=today.weekday())
            start = end - timedelta(days=7)
            return int(start.strftime("%Y%m%d")), int(end.strftime("%Y%m%d"))
        if tr == "last_3_months":
            start = today.replace(day=1)
            for _ in range(2):
                start = (start - timedelta(days=1)).replace(day=1)
            nxt = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
            return int(start.strftime("%Y%m%d")), int(nxt.strftime("%Y%m%d"))
        if tr == "last_month":
            end = today.replace(day=1)
            start = (end - timedelta(days=1)).replace(day=1)
            return int(start.strftime("%Y%m%d")), int(end.strftime("%Y%m%d"))
        if tr.startswith("last_") and tr.endswith("_days"):
            try:
                days = int(tr[len("last_"):-len("_days")])
                if days <= 0 or days > 365:
                    return None, None
                start = today - timedelta(days=days - 1)
                end = today + timedelta(days=1)
                return int(start.strftime("%Y%m%d")), int(end.strftime("%Y%m%d"))
            except ValueError:
                return None, None
        return None, None

    @staticmethod
    def _quote(value: str) -> str:
        return value.replace("'", "''")

    @staticmethod
    def _safe_limit(value, maximum=1000):
        try:
            n = int(value) if value is not None else 0
            return max(1, min(n, int(maximum))) if n else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_direction(value):
        direction = str(value or "ASC").upper()
        if direction not in {"ASC", "DESC"}:
            raise ValueError("order direction must be ASC or DESC")
        return direction

    def _safe_aggregate_order_by(self, intent, metric, resolved_dims):
        value = intent.entities.get("order_by")
        allowed = {d["alias"] for d in resolved_dims} | {metric.name}
        if isinstance(value, str):
            cleaned = value.strip()
            parts = cleaned.split()
            if parts and parts[0] in allowed and (len(parts) == 1 or parts[1].upper() in {"ASC", "DESC"}):
                return cleaned
        if isinstance(value, dict):
            field = value.get("field")
            if field in allowed:
                return f"{field} {self._safe_direction(value.get('direction', 'ASC'))}"
        return None

    def _safe_detail_order_by(self, intent, detail_view):
        value = (intent.entities or {}).get("order_by")
        if isinstance(value, dict):
            field = value.get("field")
            direction = value.get("direction", "ASC")
            if field not in detail_view.fields:
                raise ValueError(f"Unsupported detail order_by field: {field}")
            return f"{detail_view.fields[field].sql_expression} {self._safe_direction(direction)}"
        if isinstance(value, list):
            if len(value) != 1 or not isinstance(value[0], dict):
                raise ValueError("Only one semantic order_by field is supported for detail Top-N queries")
            item = value[0]
            field = item.get("field")
            if field not in detail_view.fields:
                raise ValueError(f"Unsupported detail order_by field: {field}")
            return f"{detail_view.fields[field].sql_expression} {self._safe_direction(item.get('direction', 'ASC'))}"
        if isinstance(value, str):
            # Backward-friendly but still strictly allow-listed: accept only
            # 'field' or 'field ASC/DESC', never arbitrary SQL expressions.
            parts = value.strip().split()
            if parts and parts[0] in detail_view.fields and (len(parts) == 1 or parts[1].upper() in {"ASC", "DESC"}):
                direction = self._safe_direction(parts[1] if len(parts) == 2 else "ASC")
                return f"{detail_view.fields[parts[0]].sql_expression} {direction}"
            raise ValueError("Unsupported detail order_by value")
        return None
