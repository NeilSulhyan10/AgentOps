from typing import Optional
from .base import LLMProvider
from .mock import MockLLM, DeterministicMockLLM
from .schemas import LLMRequest, LLMResponse
from backend.config import settings


_llm_instance: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = _create_llm_provider()
    return _llm_instance


def _create_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.lower()

    if provider == "mock":
        return DeterministicMockLLM()
    elif provider == "nemotron":
        from .nemotron import NemotronLLM
        return NemotronLLM(
            api_key=settings.nemotron_api_key,
            api_url=settings.nemotron_api_url,
            model=settings.nemotron_model,
            max_tokens=settings.nemotron_max_tokens,
            temperature=settings.nemotron_temperature
        )
    else:
        return DeterministicMockLLM()


def set_llm_provider(provider: LLMProvider) -> None:
    global _llm_instance
    _llm_instance = provider