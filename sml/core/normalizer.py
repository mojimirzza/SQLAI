"""Entity normalization for cross-system correlation.

P0.2 — Server identity normalization.
"""
from __future__ import annotations

# Canonical aliases: heterogeneous keys map to one canonical key.
_KEY_ALIASES: dict[str, str] = {
    "server_name": "server",
    "server_sk": "server",
    "scope_key": "server",
    "srv": "server",
}

# Optional value-level mapping (server_sk → canonical server names).
# Populated from dim_server or config at runtime.
_VALUE_MAP: dict[str, dict[str, list[str]]] = {
    "server": {},
}


def register_server_mapping(server_sk: str, server_names: list[str]) -> None:
    """Register a bidirectional server identity mapping."""
    sk = str(server_sk).strip()
    names = [n.strip().lower() for n in server_names if n and n.strip()]
    _VALUE_MAP["server"][sk] = names
    for n in names:
        _VALUE_MAP["server"].setdefault(n, [sk])


def normalize_entities(entities: dict[str, list[str]]) -> dict[str, set[str]]:
    """Return canonical {key: {normalized_values}} for overlap scoring.

    - Keys are canonicalized via _KEY_ALIASES.
    - Values are lower-cased and stripped.
    - Value-level mappings are expanded (e.g. server_sk 1 → srv-a).
    """
    out: dict[str, set[str]] = {}
    for raw_key, raw_values in (entities or {}).items():
        key = _KEY_ALIASES.get(raw_key.strip().lower(), raw_key.strip().lower())
        if key not in out:
            out[key] = set()
        for v in raw_values:
            if v is None:
                continue
            nv = str(v).strip().lower()
            out[key].add(nv)
            # Expand value aliases if known
            aliases = _VALUE_MAP.get(key, {}).get(nv, [])
            for alias in aliases:
                out[key].add(alias.strip().lower())
    return out
