"""The LLM provider interface: one async call, prompt in, text out."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel


class LLMRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4096
    # Describes the call for logs: {"task": "routing" | "analysis" | "critic" | "rca" | "remediation", ...}
    metadata: Dict[str, Any] = {}


class LLMResponse(BaseModel):
    content: str
    tokens_used: int = 0
    model: str = ""
    metadata: Dict[str, Any] = {}
    # True when the provider deliberately gave no answer (rule-based mode).
    # The caller then uses its rule-based implementation; this is not an error.
    skipped: bool = False
    # Set when the call itself failed (network, auth, timeout). Content is then unusable.
    error: Optional[str] = None


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...
