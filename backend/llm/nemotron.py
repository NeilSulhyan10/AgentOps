import json
import asyncio
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel
from openai import AsyncOpenAI

from .base import LLMProvider, LLMRequest, LLMResponse


class NemotronLLM(LLMProvider):
    def __init__(
        self,
        api_key: str,
        api_url: str,
        model: str = "nemotron-3-ultra",
        max_tokens: int = 4096,
        temperature: float = 0.1,
        timeout: float = 60.0
    ):
        self._api_key = api_key
        self._api_url = api_url.rstrip('/')
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout = timeout
        self._client: Optional[AsyncOpenAI] = None

    @property
    def provider_name(self) -> str:
        return "nemotron"

    @property
    def model_name(self) -> str:
        return self._model

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self._api_url,
                api_key=self._api_key,
                timeout=self._timeout
            )
        return self._client

    async def generate(self, request: LLMRequest) -> LLMResponse:
        client = self._get_client()

        messages = [
            {"role": "system", "content": request.system_prompt or "You are a DevOps incident investigation expert."},
            {"role": "user", "content": request.prompt}
        ]

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0

            return LLMResponse(
                content=content,
                tokens_used=tokens_used,
                model=self._model,
                metadata={"provider": "nemotron"}
            )
        except Exception as e:
            return LLMResponse(
                content=f"Error: {str(e)}",
                tokens_used=0,
                model=self._model,
                metadata={"error": str(e)}
            )

    async def generate_structured(
        self,
        request: LLMRequest,
        response_model: Type[BaseModel]
    ) -> BaseModel:
        response = await self.generate(request)
        try:
            data = json.loads(response.content)
            return response_model(**data)
        except (json.JSONDecodeError, ValueError):
            return response_model()

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None