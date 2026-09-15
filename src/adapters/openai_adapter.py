import json
import os

from openai import OpenAI
from ports.llm_port import LLMPort, StructuredOutput


class OpenAIAdapter(LLMPort):
    def __init__(self, api_key=None, model="gpt-4o-mini", base_url=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL") or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") or os.getenv("OPENROUTER_BASE_URL")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.api_key:
                raise RuntimeError("No LLM API key is configured.")
            kwargs = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def generate(self, prompt, system_prompt=None, schema=None):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        tool = {
            "type": "function",
            "function": {
                "name": "structured_response",
                "description": "Return the requested structured analysis.",
                "parameters": schema or {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "confidence": {"type": "number"},
                        "entities": {"type": "object"},
                        "needs_clarification": {"type": "boolean"},
                        "clarification_question": {"type": "string"},
                        "answer": {"type": "string"},
                    },
                    "required": ["category", "confidence", "entities", "needs_clarification"],
                },
            },
        }
        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, tools=[tool],
                tool_choice={"type": "function", "function": {"name": "structured_response"}},
                temperature=0,
            )
            call = response.choices[0].message.tool_calls[0]
            args = json.loads(call.function.arguments)
            return StructuredOutput(
                intent=args.get("category", "unknown"), confidence=float(args.get("confidence", 0)),
                entities=args.get("entities") or {}, needs_clarification=bool(args.get("needs_clarification", False)),
                clarification_question=args.get("clarification_question"), answer=args.get("answer"), data=args,
                query_type=args.get("query_type", "aggregate"), needs_business_context=bool(args.get("needs_business_context", False)),
                relevant_tables=list(args.get("relevant_tables") or []),
            )
        except Exception as exc:
            return StructuredOutput("error", 0.0, {"error": str(exc)}, True,
                "The AI service could not safely process the request.", data={"error": str(exc)})
