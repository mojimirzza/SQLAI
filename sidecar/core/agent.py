"""
ReAct Agent Engine — plain Python with optional loop-state persistence.
"""
from __future__ import annotations
import json
import uuid
from datetime import datetime
from typing import Any

try:
    from sidecar.core.tool_registry import Tool, ReActStep, AgentResult
except ImportError:  # standalone sidecar execution
    from core.tool_registry import Tool, ReActStep, AgentResult


class ReActAgent:
    """Reason → Act(tool) → Observe → Repeat with bounded, auditable state."""

    def __init__(self, llm_client, tools: list[Tool], max_steps: int = 10):
        self.llm = llm_client
        self.tools = {t.name: t for t in tools}
        self.max_steps = max_steps

    def run(
        self,
        task: str,
        system_prompt: str,
        run_id: str | None = None,
        state: Any | None = None,
        investigation_id: str | None = None,
    ) -> AgentResult:
        run_id = run_id or str(uuid.uuid4())[:8]
        trace_id = str(uuid.uuid4())[:8]
        steps: list[ReActStep] = []
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task}\nYou have access to these tools: {list(self.tools.keys())}. Think step by step."},
        ]
        previous_action = None
        retry_count = 0

        for step_num in range(1, self.max_steps + 1):
            plan = self._plan(messages)
            action = plan["action"]
            action_input = plan.get("action_input", {})
            iteration_id = str(uuid.uuid4())

            if action == "finish":
                if state is not None:
                    state.start_iteration(run_id, iteration_id, step_num, "finish", {}, plan.get("thought", ""), investigation_id, datetime.now())
                    state.finish_iteration(
                        iteration_id, observation={"answer": plan.get("answer", "")},
                        action_status="ok", verification_status="passed",
                        verification_reason="agent explicitly declared completion",
                        retry_count=retry_count, termination_reason="agent_finish",
                    )
                steps.append(ReActStep(
                    thought=plan.get("thought", ""), action="finish", action_input={}, observation=""
                ))
                return AgentResult(success=True, output=plan.get("answer", plan.get("thought", "")), steps=steps, trace_id=trace_id)

            if state is not None:
                state.start_iteration(run_id, iteration_id, step_num, action, action_input, plan.get("thought", ""), investigation_id, datetime.now())

            if action == previous_action:
                retry_count += 1
            else:
                retry_count = 0
            previous_action = action

            if action not in self.tools:
                obs = json.dumps({"status": "error", "error": f"Unknown tool: {action}"})
                action_status = "error"
                verification_status = "failed"
                verification_reason = "tool is not registered"
            else:
                try:
                    obs = self.tools[action].run(**action_input)
                    try:
                        obs_data = json.loads(obs)
                    except json.JSONDecodeError:
                        obs_data = {"status": "ok", "result": obs}
                    action_status = "ok" if obs_data.get("status") == "ok" else "error"
                    verification_status = "passed" if action_status == "ok" else "failed"
                    verification_reason = "tool returned status=ok" if action_status == "ok" else str(obs_data.get("error", "tool execution failed"))
                except Exception as exc:  # defensive boundary around tool execution
                    obs = json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)
                    action_status = "error"
                    verification_status = "failed"
                    verification_reason = str(exc)

            if state is not None:
                state.finish_iteration(
                    iteration_id, observation=obs, action_status=action_status,
                    verification_status=verification_status, verification_reason=verification_reason,
                    retry_count=retry_count,
                )

            steps.append(ReActStep(thought=plan.get("thought", ""), action=action, action_input=action_input, observation=obs))

            messages.append({
                "role": "assistant",
                "content": f"Action: {action}\nAction Input: {json.dumps(action_input, ensure_ascii=False)}",
            })
            messages.append({"role": "user", "content": f"Observation: {obs}"})

        if state is not None and steps:
            last_iteration = state.get_run_iterations(run_id)[-1]
            state.terminate_iteration(last_iteration["iteration_id"], "max_steps")

        return AgentResult(
            success=False,
            output="Agent reached maximum steps without finishing.",
            steps=steps,
            trace_id=trace_id,
        )

    def _plan(self, messages: list[dict]) -> dict:
        tools_schema = []
        for t in self.tools.values():
            tools_schema.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": {
                        "type": "object",
                        "properties": t.parameters,
                        "required": list(t.parameters.keys()),
                    },
                },
            })

        tools_schema.append({
            "type": "function",
            "function": {
                "name": "finish",
                "description": "Use this when you have enough information to answer the task.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "thought": {"type": "string", "description": "Brief decision rationale"},
                        "answer": {"type": "string", "description": "The final answer"},
                    },
                    "required": ["thought", "answer"],
                },
            },
        })

        response = self.llm.chat(messages, tools=tools_schema, tool_choice="auto")
        msg = response.choices[0].message
        if msg.tool_calls:
            call = msg.tool_calls[0]
            args = json.loads(call.function.arguments)
            return {
                "thought": args.get("thought", msg.content or ""),
                "action": call.function.name,
                "action_input": {k: v for k, v in args.items() if k not in ("thought", "answer")},
                "answer": args.get("answer", ""),
            }
        return {"thought": msg.content or "", "action": "finish", "action_input": {}, "answer": msg.content or ""}
