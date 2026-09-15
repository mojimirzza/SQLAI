import yaml
from ports.semantic_layer_port import (
    SemanticLayerPort,
    MetricDefinition,
    DetailFieldDefinition,
    DetailViewDefinition,
)


class YAMLSemanticAdapter(SemanticLayerPort):
    def __init__(self, yaml_path):
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self.join_graph = {j["table"]: j for j in data.get("join_graph", [])}
        self.canonical_values = data.get("canonical_values", {})
        self.metrics = {}
        for name, d in data.get("metrics", {}).items():
            self.metrics[name] = MetricDefinition(
                name, d["sql_expression"], d["table"],
                d.get("dimensions", []), d.get("filters", []), d.get("description", ""),
                joins=d.get("joins", [])
            )

        self.detail_views = {}
        for name, d in data.get("detail_views", {}).items():
            fields = {}
            for field_name, fd in d.get("fields", {}).items():
                fields[field_name] = DetailFieldDefinition(
                    name=field_name,
                    sql_expression=fd["sql_expression"],
                    alias=fd.get("alias", field_name),
                    description=fd.get("description", ""),
                )
            self.detail_views[name] = DetailViewDefinition(
                name=name,
                table=d["table"],
                fields=fields,
                joins=d.get("joins", []),
                default_fields=d.get("default_fields", list(fields)),
                max_limit=int(d.get("max_limit", 100)),
                description=d.get("description", ""),
            )

    def get_metric(self, name): return self.metrics.get(name)
    def list_metrics(self): return list(self.metrics)
    def get_detail_view(self, name): return self.detail_views.get(name)
    def list_detail_views(self): return list(self.detail_views)
    def get_join(self, table): return self.join_graph.get(table)

    def get_canonical_value(self, field, value):
        """Return the semantic-layer canonical spelling for a string enum value."""
        values = self.canonical_values.get(field, [])
        if not isinstance(value, str):
            return value
        lowered = value.casefold()
        for candidate in values:
            if isinstance(candidate, str) and candidate.casefold() == lowered:
                return candidate
        return value
