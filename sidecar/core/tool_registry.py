"""
Micro-Agent Framework — ReAct pattern with Tool decorators.
Zero external framework dependencies. ~80 lines.
"""
from __future__ import annotations
import json
import inspect
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class Tool:
    """A tool the agent can invoke."""
    name: str
    description: str
    parameters: dict[str, Any]
    func: Callable

    def run(self, **kwargs) -> str:
        """Execute the tool and return a string observation."""
        try:
            result = self.func(**kwargs)
            return json.dumps({"status": "ok", "result": result}, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False)


def tool(name: str | None = None, description: str | None = None):
    """Decorator to register a function as an agent tool."""
    def decorator(func: Callable) -> Tool:
        tool_name = name or func.__name__
        tool_desc = description or (func.__doc__ or "").strip()
        sig = inspect.signature(func)
        params = {}
        for param_name, param in sig.parameters.items():
            param_type = "string"
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
            elif param.annotation == list or getattr(param.annotation, "__origin__", None) is list:
                param_type = "array"
            params[param_name] = {
                "type": param_type,
                "description": f"Parameter {param_name}",
            }
        return Tool(
            name=tool_name,
            description=tool_desc,
            parameters=params,
            func=func,
        )
    return decorator


@dataclass
class ReActStep:
    """One step in the ReAct loop."""
    thought: str
    action: str          # tool name or "finish"
    action_input: dict
    observation: str = ""


@dataclass
class AgentResult:
    """Final result from an agent run."""
    success: bool
    output: str
    steps: list[ReActStep] = field(default_factory=list)
    trace_id: str = ""
