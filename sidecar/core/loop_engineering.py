"""
Loop engineering utilities for the sidecar.

This module keeps the loop contract explicit without coupling the ReAct engine
itself to SQLite.  It provides structural verification, run replay/audit, and
simple evaluation helpers suitable for deterministic CI tests.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class VerificationResult:
    status: str
    reason: str


class LoopVerifier:
    """Verify structural invariants of a persisted agent run."""

    REQUIRED_EVENT_FIELDS = {
        "iteration_id", "run_id", "iteration_no", "decision_action", "decision_reason",
        "action_status", "verification_status"
    }

    def verify_trace(self, iterations: list[dict[str, Any]]) -> VerificationResult:
        if not iterations:
            return VerificationResult("failed", "no iterations recorded")

        expected = 1
        for row in iterations:
            missing = self.REQUIRED_EVENT_FIELDS - set(row)
            if missing:
                return VerificationResult("failed", f"missing fields: {sorted(missing)}")
            if row["iteration_no"] != expected:
                return VerificationResult(
                    "failed", f"iteration sequence broken at {row['iteration_no']}, expected {expected}"
                )
            if not row.get("run_id"):
                return VerificationResult("failed", "iteration has no run_id")
            if not row.get("iteration_id"):
                return VerificationResult("failed", "iteration has no iteration_id")
            expected += 1

        terminal = iterations[-1]
        if terminal.get("decision_action") == "finish":
            if terminal.get("termination_reason") not in {"goal_reached", "agent_finish"}:
                return VerificationResult("failed", "finish iteration lacks a valid termination reason")
        elif terminal.get("termination_reason") != "max_steps":
            return VerificationResult("failed", "non-finish terminal iteration lacks termination reason")

        return VerificationResult("passed", "trace is structurally complete")


class LoopEvaluator:
    """Lightweight evaluation of loop quality from a persisted trace."""

    def evaluate(self, iterations: list[dict[str, Any]]) -> dict[str, Any]:
        if not iterations:
            return {"score": 0.0, "passed": False, "reasons": ["no iterations"]}

        total = len(iterations)
        verified = sum(1 for x in iterations if x.get("verification_status") == "passed")
        errors = sum(1 for x in iterations if x.get("action_status") == "error")
        unique_actions = len({x.get("decision_action") for x in iterations})
        decision_diversity = min(1.0, unique_actions / 2.0)
        verification_ratio = verified / total
        error_penalty = min(0.4, errors / max(1, total) * 0.4)
        score = max(0.0, min(1.0, 0.5 * verification_ratio + 0.5 * decision_diversity - error_penalty))

        reasons: list[str] = []
        if unique_actions <= 1 and total > 1:
            reasons.append("loop repeatedly selected the same action")
        if errors:
            reasons.append(f"{errors} tool execution error(s)")
        if not errors and verified == total:
            reasons.append("all tool actions passed execution verification")

        return {"score": round(score, 3), "passed": score >= 0.6, "reasons": reasons}


class LoopReplay:
    """Replay an existing trace without executing tools or calling the LLM."""

    def replay(self, iterations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        replayed = []
        for row in iterations:
            replayed.append({
                "iteration_no": row["iteration_no"],
                "decision_action": row["decision_action"],
                "decision_reason": row.get("decision_reason", ""),
                "action_input": _load_json(row.get("action_input_json"), {}),
                "observation": _load_json(row.get("observation_json"), row.get("observation", "")),
                "action_status": row.get("action_status"),
                "verification_status": row.get("verification_status"),
            })
        return replayed


def _load_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
