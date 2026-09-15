"""
Dual Synthesizer with Baseline Enrichment Support
-------------------------------------------------
Consumes BaselineMetrics to provide context-aware answers.
"""
from core.models import Persona
from core.baseline_models import BaselineMetrics
from ports.llm_port import LLMPort


class BaselineAwareDualSynthesizer:
    """
    Wraps the original DualSynthesizer to inject baseline context into prompts.
    Falls back to original behavior if no baseline provided.
    """

    def __init__(self, llm: LLMPort, ba_prompt_path="prompts/ba_system_baseline.md", ceo_prompt_path="prompts/ceo_system_baseline.md"):
        self.llm = llm
        with open(ba_prompt_path, encoding="utf-8") as f:
            self._ba_system = f.read()
        with open(ceo_prompt_path, encoding="utf-8") as f:
            self._ceo_system = f.read()

    def synthesize(self, persona: Persona, query: str, sql: str, results: list[dict],
                   context: dict, baseline: BaselineMetrics | None = None) -> str:
        system = self._ba_system if persona == Persona.BUSINESS_ANALYST else self._ceo_system

        prompt = (
            f"Original question: {query}\n"
            f"Executed SQL: {sql}\n"
            f"Results (up to 20 rows): {results[:20]}\n"
            f"Business context: {context.get('business_context', [])}"
        )

        if baseline and baseline.current_value is not None:
            prompt += "\n\n" + baseline.to_prompt_context()

        result = self.llm.generate(prompt, system)
        return result.answer or "No answer generated."
