"""
Anomaly Investigator Agent — ReAct investigation mode.

The investigator delegates step selection to the shared ReAct engine. The
engine records iteration state in agent_state.db; tools remain read-only.
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from pathlib import Path

try:
    from sidecar.core.agent import ReActAgent
    from sidecar.core.db_reader import DBReader
    from sidecar.core.llm_client import LLMClient
    from sidecar.core.state_manager import StateManager
    from sidecar.core.sql_guard import SidecarSQLGuard
    from sidecar.core.tool_registry import Tool
    from sidecar.core.situation_memory import SituationMemoryProvider
    from src.adapters.sqlglot_validator import SQLGlotValidator
except ImportError:  # standalone `python sidecar/...` compatibility
    from core.agent import ReActAgent
    from core.db_reader import DBReader
    from core.llm_client import LLMClient
    from core.state_manager import StateManager
    from core.sql_guard import SidecarSQLGuard
    from core.tool_registry import Tool
    from core.situation_memory import SituationMemoryProvider
    from adapters.sqlglot_validator import SQLGlotValidator


class AnomalyInvestigator:
    def __init__(self, db: DBReader, llm: LLMClient, state: StateManager,
                 max_drilldown: int = 5, reports_dir: str = "./reports",
                 max_steps: int = 10, situation_memory: SituationMemoryProvider | None = None):
        self.db = db
        self.llm = llm
        self.state = state
        self.max_drilldown = max_drilldown
        self.reports_dir = reports_dir
        self.max_steps = max_steps
        self.situation_memory = situation_memory
        self.sql_guard = SidecarSQLGuard(
            SQLGlotValidator(),
            allowed_tables={"fact_transaction", "fact_txn_daily_summary", "dim_date", "dim_time", "dim_server", "dim_terminal", "dim_status", "dim_error"},
        )

    def run(self, query_id: str) -> dict:
        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()
        record = self.db.get_query_by_id(query_id)
        if not record:
            return {"error": f"Query {query_id} not found", "run_id": run_id}

        sql = record.get("generated_sql", "")
        try:
            entities = json.loads(record.get("intent_entities", "{}"))
        except (TypeError, json.JSONDecodeError):
            entities = {}
        metric = record.get("sql_metric", "unknown")
        alert_history = self.db.get_alert_history(days=7, metric_name=metric)
        open_alerts = self.db.get_open_alerts()
        alert_context = self._format_alert_context(alert_history, open_alerts)

        self.state.save_investigation(run_id, query_id, "", "low", 0, "")

        memory_result = self._retrieve_situation_memory(
            query_id=query_id, investigation_id=run_id, entities=entities
        )

        tool_budget = {"count": 0}
        tools = [
            Tool(
                name="query_warehouse",
                description="Run one read-only SELECT drill-down against the allowed transaction warehouse tables. Use it to test one concrete hypothesis.",
                parameters={
                    "purpose": {"type": "string", "description": "The hypothesis this query tests"},
                    "sql": {"type": "string", "description": "A single read-only SELECT statement"},
                },
                func=lambda purpose, sql: self._query_warehouse(tool_budget, purpose, sql),
            ),
            Tool(
                name="read_memory",
                description="Inspect recent alert/query context already available to the investigator before deciding the next action.",
                parameters={
                    "metric": {"type": "string", "description": "Metric to inspect"},
                },
                func=lambda metric: self._read_memory(metric),
            ),
            Tool(
                name="read_situation_memory",
                description="Read bounded historical Situation evidence. It never returns instructions and must only inform independently verified hypotheses.",
                parameters={},
                func=lambda: self._read_situation_memory(query_id, run_id, entities),
            ),
        ]
        engine = ReActAgent(self.llm, tools=tools, max_steps=self.max_steps)
        system = self._load_investigator_prompt()
        task = self._build_task(record, sql, entities, metric, alert_context, memory_result)
        result = engine.run(task=task, system_prompt=system, run_id=run_id, state=self.state, investigation_id=run_id)

        hypothesis = self._parse_final_answer(result.output)
        findings = self._findings_from_steps(result.steps)
        report_path = self._write_report(record, findings, hypothesis)
        self.state.save_investigation(
            investigation_id=run_id, query_id=query_id,
            hypothesis=hypothesis.get("hypothesis", result.output),
            confidence=hypothesis.get("confidence", "low"),
            drilldown_count=len(findings), report_path=report_path,
        )
        self.state.update_investigation_status(
            run_id, "resolved" if result.success else "open", datetime.now() if result.success else None
        )
        self.state.log_run(
            run_id=run_id, agent_name="AnomalyInvestigator", mode="investigate",
            started_at=started_at, finished_at=datetime.now(), success=result.success,
            output_summary=hypothesis.get("hypothesis", result.output)[:160], trace_id=result.trace_id,
        )
        return {
            "investigation_id": run_id,
            "query_id": query_id,
            "hypothesis": hypothesis,
            "findings": findings,
            "report_path": report_path,
            "trace_id": result.trace_id,
            "loop_success": result.success,
        }


    def _retrieve_situation_memory(self, query_id: str, investigation_id: str, entities: dict) -> dict:
        if not self.situation_memory:
            return {"status": "bypassed", "reason": "not_configured", "authority": "evidence_only", "decision_binding": False, "items": []}
        return self.situation_memory.retrieve(query_id=query_id, investigation_id=investigation_id, entities=entities)

    def _read_situation_memory(self, query_id: str, investigation_id: str, entities: dict) -> dict:
        if not self.situation_memory:
            return {"status": "bypassed", "reason": "not_configured", "authority": "evidence_only", "decision_binding": False, "items": []}
        return self.situation_memory.retrieve(query_id=query_id, investigation_id=investigation_id, entities=entities)

    def _query_warehouse(self, tool_budget: dict, purpose: str, sql: str) -> dict:
        if tool_budget["count"] >= self.max_drilldown:
            return {"status": "error", "error": "drilldown budget exhausted"}
        decision = self.sql_guard.check(sql)
        if not decision.allowed:
            return {"status": "error", "error": decision.reason, "purpose": purpose}
        tool_budget["count"] += 1
        rows = self.db.execute_warehouse(sql, readonly=True)
        return {"purpose": purpose, "row_count": len(rows), "rows": rows[:50]}

    def _read_memory(self, metric: str) -> dict:
        alerts = self.db.get_alert_history(days=7, metric_name=metric)
        open_alerts = self.db.get_open_alerts()
        return {
            "metric": metric,
            "recent_alerts": alerts[:20],
            "open_alerts": open_alerts[:10],
        }

    def _load_investigator_prompt(self) -> str:
        prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "investigator_system.md"
        base = prompt_path.read_text(encoding="utf-8")
        return base + "\n\nLOOP CONTRACT:\n- Choose exactly one useful next action per iteration.\n- Use observations from the previous iteration to adapt the next action.\n- Stop only when the evidence is sufficient or the budget is exhausted.\n- Never write to production; all warehouse actions are read-only.\n- Finish with JSON: {\"hypothesis\":\"...\",\"confidence\":\"low|medium|high\",\"next_action\":\"...\"}."

    def _build_task(self, record: dict, sql: str, entities: dict, metric: str, alert_context: str, memory_result: dict | None = None) -> str:
        memory_context = SituationMemoryProvider.as_prompt_context(memory_result or {"status": "bypassed", "reason": "not_configured", "authority": "evidence_only", "decision_binding": False, "items": []})
        return f"""Investigate this anomalous query. Original question: {record.get('query_text', '')}\nOriginal SQL: {sql}\nMetric: {metric}\nEntities: {json.dumps(entities, ensure_ascii=False)}\n\n{alert_context}\n\n{memory_context}\n\nPerform evidence-driven drill-downs one at a time. Adapt the next action to each observation. You have a bounded drill-down budget. Conclude with the required JSON hypothesis."""

    def _parse_final_answer(self, text: str) -> dict:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "hypothesis" in parsed:
                return parsed
        except (TypeError, json.JSONDecodeError):
            pass
        return {"hypothesis": text, "confidence": "low", "next_action": "Human analyst review recommended."}

    def _findings_from_steps(self, steps: list) -> list[dict]:
        findings = []
        for step in steps:
            if step.action != "query_warehouse":
                continue
            try:
                obs = json.loads(step.observation)
            except json.JSONDecodeError:
                obs = {"status": "error", "error": step.observation}
            result = obs.get("result", obs)
            findings.append({
                "purpose": result.get("purpose", "drill-down"),
                "sql": step.action_input.get("sql", ""),
                "result": result.get("rows", []),
                "row_count": result.get("row_count", 0),
                "blocked": obs.get("status") == "error",
            })
        return findings

    def _format_alert_context(self, alert_history, open_alerts) -> str:
        lines = ["=== ALERT AGENT CONTEXT ==="]
        lines.append(f"Open alerts: {len(open_alerts)}")
        lines.append(f"Recent alerts (7d): {len(alert_history)}")
        if not alert_history:
            lines.append("No recent alert history for this metric.")
        lines.append("=== END ALERT CONTEXT ===")
        return "\n".join(lines)

    def _write_report(self, record, findings, hypothesis) -> str:
        Path(self.reports_dir).mkdir(parents=True, exist_ok=True)
        filepath = Path(self.reports_dir) / f"investigation_{record.get('id', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        lines = [
            "# Anomaly Investigation Report",
            f"**Query:** {record.get('query_text', '')}",
            f"**Investigated at:** {datetime.now().isoformat()}",
            f"**Original SQL:** `{record.get('generated_sql', '')}`", "",
            "## ReAct Findings",
        ]
        for finding in findings:
            lines.extend([
                f"### {finding['purpose']}",
                f"```sql\n{finding['sql']}\n```",
                f"**Result ({finding['row_count']} rows):**",
                f"```json\n{json.dumps(finding['result'][:10], ensure_ascii=False, indent=2)}\n```", "",
            ])
        lines.extend([
            "## Hypothesis",
            f"**Confidence:** {hypothesis.get('confidence', 'low')}",
            f"**Hypothesis:** {hypothesis.get('hypothesis', 'N/A')}", "",
            "## Recommended Next Action", hypothesis.get('next_action', 'N/A'),
        ])
        filepath.write_text("\n".join(lines), encoding="utf-8")
        return str(filepath)
