"""Rule-based mode: there is no LLM, so every agent step uses its deterministic implementation."""

from .base import LLMProvider, LLMRequest, LLMResponse


class RulesOnlyLLM(LLMProvider):
    """
    A provider that never answers.

    The agent runner sees ``skipped=True`` and runs the rule-based version of
    the step (keyword router, pattern-matching specialists, rule critic,
    template RCA).  Investigations are then offline, free and repeatable.
    """

    @property
    def provider_name(self) -> str:
        return "rules"

    @property
    def model_name(self) -> str:
        return "none"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(content="", skipped=True)
