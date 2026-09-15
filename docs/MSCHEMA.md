# M-Schema Enrichment

M-Schema is a **build-time schema metadata artifact** used only to enrich the LLM context for intent extraction and semantic SQL review. It does not replace the ITXN semantic layer and it is not consulted by the deterministic SQL generator.

## Source of truth and precedence

1. Physical database metadata (types/keys) is compiled when a database is available.
2. `docs/table_descriptions.yaml` supplies human-readable table/column descriptions when available.
3. `src/config/semantic_layer.yaml` supplies metric-aware descriptions and logical join relationships.
4. The semantic layer remains authoritative for supported metrics, dimensions, joins, and SQL generation.
5. M-Schema is presentation/context metadata for the LLM only.

## Build

```bash
python scripts/mschema_compiler.py --db data/bank.duckdb --output src/config/mschema.yaml
```

The compiler supports DuckDB (`.duckdb`, `.ddb`) and SQLite (`.db`, `.sqlite`, `.sqlite3`). Runtime query processing does **not** introspect the database.

Real sample values are opt-in and restricted to an explicit allow-list:

```bash
python scripts/mschema_compiler.py --db data/bank.duckdb --allow-real-samples
```

Sensitive columns are never sampled unless explicitly allow-listed. The default is safe: no raw real sample values are copied.

## Runtime use

`ContextBuilder` loads the artifact once at startup and returns an optional `mschema` section. `IntentExtractor` and the memory-aware intent wrapper may include the same artifact in their prompt context. `SQLReviewer` receives it through the existing context dictionary.

If the artifact is absent or invalid, the Core falls back to its existing schema context and continues to operate.

## Important limitations

The repository baseline may not contain `data/bank.duckdb`. In that case `src/config/mschema.yaml` is a metadata-only baseline generated from the checked-in documentation/semantic contracts. A deployment/build with the real DuckDB should regenerate the artifact so physical types, physical keys, and approved sample values are current.
