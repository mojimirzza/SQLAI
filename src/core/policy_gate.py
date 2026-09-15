from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


class PolicyGate:
    """Deterministic authorization/policy enforcement before execution."""

    def __init__(self, policies: dict):
        self.policies = policies or {}
        self.role_rules = self.policies.get("role_rules", {}) or {}
        self.protected_tables = {str(x).lower() for x in self.policies.get("protected_tables", [])}

    def authorize_query(self, role: str) -> PolicyDecision:
        role = (role or "").strip().lower()
        allowed_roles = self.role_rules.get("query", [])
        if allowed_roles and role not in {str(x).lower() for x in allowed_roles}:
            return PolicyDecision(False, f"Role '{role or 'unknown'}' is not allowed to execute warehouse queries.")
        return PolicyDecision(True)

    def authorize_memory(self, requester_id: str, target_id: str, role: str) -> PolicyDecision:
        role = (role or "").strip().lower()
        admins = {str(x).lower() for x in self.role_rules.get("memory_admin", [])}
        if requester_id == target_id or role in admins:
            return PolicyDecision(True)
        return PolicyDecision(False, "Memory access is restricted to the requesting user or a memory-admin role.")

    def validate_tables(self, tables: Iterable[str]) -> PolicyDecision:
        forbidden = sorted({str(t).lower() for t in tables} & self.protected_tables)
        if forbidden:
            return PolicyDecision(False, f"Protected tables cannot be queried: {', '.join(forbidden)}")
        return PolicyDecision(True)
