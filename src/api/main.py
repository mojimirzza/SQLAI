"""Canonical ITXN API entrypoint.

The enriched Stage-4 application is the supported runtime surface. This
compatibility module intentionally keeps ``src.api.main:app`` stable for
Docker/uvicorn callers while delegating to ``main_enriched``.
"""
from .main_enriched import app, QueryReq, handle_query, health, get_user_memory

__all__ = ["app", "QueryReq", "handle_query", "health", "get_user_memory"]
