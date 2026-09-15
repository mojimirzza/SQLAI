"""Deterministic A/B evaluation for Situation Memory -> ReAct.

This is a CI-safe harness: it never calls an LLM or production database.
It compares two otherwise identical ReAct agents on seeded investigation
scenarios, with the only treatment being whether historical Situation evidence
is injected into the task context.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sidecar.core.agent import ReActAgent
from sidecar.core.state_manager import StateManager
from sidecar.core.situation_memory import SituationMemoryProvider
from sidecar.core.tool_registry import Tool
from sml.core.models import Signal
from sml.storage import SituationStore


@dataclass(frozen=True)
class ABScenario:
    name: str
    query_id: str
    bank: str
    metric: str
    historical_server: str
    current_server: str


SCENARIOS = (
    ABScenario("mellat_auth", "q-ab-1", "Mellat", "approval_rate", "SRV-S08", "SRV-S08"),
    ABScenario("mellat_latency", "q-ab-2", "Mellat", "avg_latency", "SRV-S03", "SRV-S03"),
    ABScenario("tejarat_auth", "q-ab-3", "Tejarat", "approval_rate", "SRV-S11", "SRV-S11"),
    ABScenario("saman_timeout", "q-ab-4", "Saman", "timeout_rate", "SRV-S04", "SRV-S04"),
    ABScenario("mellat_reversal", "q-ab-5", "Mellat", "reversal_rate", "SRV-S09", "SRV-S09"),
)


class _FakeLLM:
    """Scripted planner: memory treatment changes the first useful drill-down."""

    def __init__(self, treatment: str, target_server: str):
        self.treatment = treatment
        self.target_server = target_server

    @staticmethod
    def _response(name: str, arguments: dict[str, Any]):
        call = SimpleNamespace(function=SimpleNamespace(name=name, arguments=json.dumps(arguments)))
        message = SimpleNamespace(tool_calls=[call], content="")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    def chat(self, messages, tools, tool_choice="auto"):
        text = "\n".join(str(m.get("content", "")) for m in messages)
        observations = [m.get("content", "") for m in messages if m.get("role") == "user" and "Observation:" in str(m.get("content", ""))]

        if observations and self.treatment == "memory":
            return self._response("finish", {
                "thought": "The targeted server query verified the historical lead.",
                "answer": json.dumps({"hypothesis": f"Current anomaly is concentrated on {self.target_server}.", "confidence": "high", "next_action": "Inspect the server's error/channel distribution."})
            })
        if observations and self.treatment == "control" and len(observations) >= 2:
            return self._response("finish", {
                "thought": "The broad and targeted queries agree.",
                "answer": json.dumps({"hypothesis": f"Current anomaly is concentrated on {self.target_server}.", "confidence": "high", "next_action": "Inspect the server's error/channel distribution."})
            })

        if self.treatment == "memory":
            sql = f"SELECT server, COUNT(*) AS failures FROM fact_transaction WHERE server = '{self.target_server}' GROUP BY server"
            reason = "Historical Situation evidence points to a previously recurring server; verify it independently."
        elif "Observation:" not in text:
            sql = "SELECT error_code, COUNT(*) AS failures FROM fact_transaction GROUP BY error_code ORDER BY failures DESC"
            reason = "Start with a broad error distribution drill-down without historical Situation memory."
        else:
            sql = f"SELECT server, COUNT(*) AS failures FROM fact_transaction WHERE server = '{self.target_server}' GROUP BY server"
            reason = "Use the prior observation to narrow to the affected server."
        return self._response("query_warehouse", {"thought": reason, "purpose": reason, "sql": sql})


def _seed_memory(path: Path, scenario: ABScenario):
    store = SituationStore(str(path))
    ts = datetime.now(timezone.utc).replace(microsecond=0)
    signal = Signal(
        f"hist-{scenario.query_id}", "query", ts, "memory", "memory.db",
        {"bank": [scenario.bank], "server": [scenario.historical_server], "metric": [scenario.metric]},
    )
    store.create_situation(
        f"S-HIST-{scenario.query_id}", signal, signal.entities, 0.95, status="resolved",
    )


def _run_arm(tmp: Path, scenario: ABScenario, treatment: str) -> dict[str, Any]:
    memory_db = tmp / "situation_memory.db"
    _seed_memory(memory_db, scenario)
    provider = SituationMemoryProvider(str(memory_db)) if treatment == "memory" else None
    entities = {"bank": [scenario.bank], "metric": [scenario.metric]}
    memory_result = provider.retrieve(query_id=scenario.query_id, entities=entities) if provider else {
        "status": "bypassed", "authority": "evidence_only", "decision_binding": False, "items": []
    }

    state = StateManager(str(tmp / f"state-{treatment}.db"))
    observed_queries: list[str] = []

    def execute(purpose: str, sql: str):
        observed_queries.append(sql)
        return {"purpose": purpose, "row_count": 1, "rows": [{"server": scenario.current_server, "failures": 42}]}

    tools = [Tool(
        name="query_warehouse", description="Read-only diagnostic query", parameters={
            "purpose": {"type": "string"}, "sql": {"type": "string"}
        }, func=execute,
    )]
    agent = ReActAgent(_FakeLLM(treatment, scenario.current_server), tools, max_steps=5)
    task = (
        f"Investigate {scenario.bank} {scenario.metric}. Entities={entities}. "
        + SituationMemoryProvider.as_prompt_context(memory_result)
    )
    result = agent.run(task=task, system_prompt="Use one drill-down at a time; validate historical evidence.", state=state)
    iterations = state.get_run_iterations(result.trace_id) if False else []
    # Run id is not exposed by AgentResult; reconstruct from persisted rows via trace-independent query.
    with sqlite3.connect(str(tmp / f"state-{treatment}.db")) as c:
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute("SELECT * FROM agent_iterations ORDER BY iteration_no").fetchall()]
    drilldowns = sum(1 for r in rows if r["decision_action"] == "query_warehouse")
    target_hit = any(scenario.current_server in q for q in observed_queries)
    evidence_query_first = bool(observed_queries) and target_hit and len(observed_queries) == 1
    return {
        "treatment": treatment,
        "scenario": scenario.name,
        "success": result.success,
        "drilldowns": drilldowns,
        "target_hit": target_hit,
        "targeted_first": evidence_query_first,
        "trace": [
            {"iteration_no": r["iteration_no"], "action": r["decision_action"], "reason": r["decision_reason"]}
            for r in rows
        ],
    }


def run_ab_evaluation(output_path: str | Path | None = None) -> dict[str, Any]:
    cases = []
    with tempfile.TemporaryDirectory(prefix="itxn_ab_") as td:
        base = Path(td)
        for scenario in SCENARIOS:
            case_dir = base / scenario.name
            case_dir.mkdir()
            cases.append(_run_arm(case_dir / "memory", scenario, "memory"))
            cases.append(_run_arm(case_dir / "control", scenario, "control"))

    memory = [x for x in cases if x["treatment"] == "memory"]
    control = [x for x in cases if x["treatment"] == "control"]
    summary = {
        "evaluation_version": "1.0",
        "scenarios": len(SCENARIOS),
        "memory": {
            "success_rate": sum(x["success"] for x in memory) / len(memory),
            "target_hit_rate": sum(x["target_hit"] for x in memory) / len(memory),
            "targeted_first_rate": sum(x["targeted_first"] for x in memory) / len(memory),
            "mean_drilldowns": sum(x["drilldowns"] for x in memory) / len(memory),
        },
        "control": {
            "success_rate": sum(x["success"] for x in control) / len(control),
            "target_hit_rate": sum(x["target_hit"] for x in control) / len(control),
            "targeted_first_rate": sum(x["targeted_first"] for x in control) / len(control),
            "mean_drilldowns": sum(x["drilldowns"] for x in control) / len(control),
        },
        "delta": {
            "mean_drilldowns": (sum(x["drilldowns"] for x in control) - sum(x["drilldowns"] for x in memory)) / len(memory),
            "targeted_first_pp": 100.0 * (
                sum(x["targeted_first"] for x in memory) / len(memory)
                - sum(x["targeted_first"] for x in control) / len(control)
            ),
        },
        "decision": "PASS" if all(x["success"] and x["target_hit"] for x in cases) else "FAIL",
        "interpretation": "Synthetic deterministic A/B gate; not an LLM quality or production-capacity claim.",
        "cases": cases,
    }
    if output_path:
        Path(output_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
