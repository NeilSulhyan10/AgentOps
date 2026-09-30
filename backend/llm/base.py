from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel


class LLMRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4096
    metadata: Dict[str, Any] = {}


class LLMResponse(BaseModel):
    content: str
    tokens_used: int = 0
    model: str = ""
    metadata: Dict[str, Any] = {}


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        pass

    @abstractmethod
    async def generate_structured(
        self,
        request: LLMRequest,
        response_model: type[BaseModel]
    ) -> BaseModel:
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass