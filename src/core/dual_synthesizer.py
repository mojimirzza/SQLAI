from core.models import Persona
from ports.llm_port import LLMPort

class DualSynthesizer:
    def __init__(self, llm: LLMPort, ba_prompt_path="prompts/ba_system.md", ceo_prompt_path="prompts/ceo_system.md"):
        self.llm = llm
        with open(ba_prompt_path, encoding="utf-8") as f:
            self._ba_system = f.read()
        with open(ceo_prompt_path, encoding="utf-8") as f:
            self._ceo_system = f.read()

    def synthesize(self, persona: Persona, query: str, sql: str, results: list[dict], context: dict) -> str:
        system = self._ba_system if persona == Persona.BUSINESS_ANALYST else self._ceo_system
        prompt = (
            f"Original question: {query}\nExecuted SQL: {sql}\n"
            f"Results (up to 20 rows): {results[:20]}\n"
            f"Business context: {context.get('business_context', [])}"
        )
        result = self.llm.generate(prompt, system)
        return result.answer or "No answer generated."
