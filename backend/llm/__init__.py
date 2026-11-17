"""
LLM layer.  ``get_llm_provider()`` returns the one provider the agents talk to:

    FAULT_INJECTION=<name>   -> FaultInjectingLLM  (backend/faults.py, demo runs)
    LLM_PROVIDER=nemotron    -> NemotronLLM        (real model, needs NEMOTRON_API_KEY)
    LLM_PROVIDER=rules       -> RulesOnlyLLM       (default: no LLM, rule-based decisions)
"""

import logging
from typing import Optional

from backend.config import settings

from .base import LLMProvider, LLMRequest, LLMResponse
from .rules import RulesOnlyLLM

logger = logging.getLogger(__name__)

_llm_instance: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = _create_llm_provider()
    return _llm_instance


def reset_llm_provider() -> None:
    """Forget the cached provider so the next call re-reads the settings."""
    global _llm_instance
    _llm_instance = None


def set_llm_provider(provider: LLMProvider) -> None:
    global _llm_instance
    _llm_instance = provider


def _create_llm_provider() -> LLMProvider:
    if settings.fault_injection:
        from backend.faults import FaultInjectingLLM  # imported here: faults.py imports this package
        return FaultInjectingLLM(settings.fault_injection)

    provider = settings.llm_provider.lower()
    if provider == "nemotron":
        from .nemotron import NemotronLLM
        return NemotronLLM(
            api_key=settings.nemotron_api_key,
            api_url=settings.nemotron_api_url,
            model=settings.nemotron_model,
            max_tokens=settings.nemotron_max_tokens,
            temperature=settings.nemotron_temperature,
        )
    if provider not in ("rules", "mock"):  # "mock" is the old name for rule-based mode
        logger.warning("Unknown LLM_PROVIDER '%s'; using rule-based mode.", provider)
    return RulesOnlyLLM()


__all__ = [
    "LLMProvider", "LLMRequest", "LLMResponse", "RulesOnlyLLM",
    "get_llm_provider", "reset_llm_provider", "set_llm_provider",
]
