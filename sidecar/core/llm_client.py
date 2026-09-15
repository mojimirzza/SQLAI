"""
LLM Client — Thin wrapper over OpenAI with structured output support.
"""
from __future__ import annotations
import os
from typing import Any

from openai import OpenAI


class LLMClient:
    """Minimal LLM client. Supports chat completions and structured JSON output."""

    def __init__(self, model: str = "gpt-4o-mini", temperature: float = 0.0,
                 max_tokens: int = 2000, api_key: str | None = None):
        self.model = os.getenv("SIDECAR_MODEL") or os.getenv("OPENROUTER_MODEL") or model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        self._base_url = os.getenv("OPENROUTER_BASE_URL") if os.getenv("OPENROUTER_API_KEY") else os.getenv("OPENAI_BASE_URL")

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("OPENAI_API_KEY not configured. Set env var or pass api_key.")
            kwargs = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             tool_choice: str | dict = "auto") -> Any:
        """Raw chat completion."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        return self.client.chat.completions.create(**kwargs)

    def generate(self, prompt: str, system: str | None = None,
                 schema: dict | None = None) -> dict:
        """Generate structured output (JSON) from LLM."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        if schema:
            tool = {
                "type": "function",
                "function": {
                    "name": "structured_response",
                    "description": "Return structured data.",
                    "parameters": schema,
                },
            }
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": "structured_response"}},
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            call = response.choices[0].message.tool_calls[0]
            import json
            return json.loads(call.function.arguments)
        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return {"answer": response.choices[0].message.content or ""}
