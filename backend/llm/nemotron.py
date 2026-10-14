import json
import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel
from openai import AsyncOpenAI

from .base import LLMProvider, LLMRequest, LLMResponse
from backend.config import settings

logger = logging.getLogger(__name__)


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
        self._trace_lock = asyncio.Lock()

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
        started_at = time.perf_counter()
        trace_id = str(uuid.uuid4())
        system_prompt = request.system_prompt or "You are a DevOps incident investigation expert."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.prompt}
        ]

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )

            content = response.choices[0].message.content or ""
            tokens_used = response.usage.total_tokens if response.usage else 0

            result = LLMResponse(
                content=content,
                tokens_used=tokens_used,
                model=self._model,
                metadata={"provider": "nemotron"}
            )
            await self._write_trace(
                trace_id=trace_id,
                request=request,
                system_prompt=system_prompt,
                response=content,
                tokens_used=tokens_used,
                duration_ms=(time.perf_counter() - started_at) * 1000,
            )
            return result
        except Exception as e:
            error_content = f"Error: {str(e)}"
            await self._write_trace(
                trace_id=trace_id,
                request=request,
                system_prompt=system_prompt,
                response=error_content,
                tokens_used=0,
                duration_ms=(time.perf_counter() - started_at) * 1000,
                error=str(e),
            )
            return LLMResponse(
                content=error_content,
                tokens_used=0,
                model=self._model,
                metadata={"error": str(e)}
            )

    async def _write_trace(
        self,
        trace_id: str,
        request: LLMRequest,
        system_prompt: str,
        response: str,
        tokens_used: int,
        duration_ms: float,
        error: Optional[str] = None,
    ) -> None:
        if not settings.llm_trace_enabled:
            return

        record = {
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": self.provider_name,
            "model": self.model_name,
            "task": request.metadata,
            "system_prompt": system_prompt,
            "prompt": request.prompt,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "response": response,
            "tokens_used": tokens_used,
            "duration_ms": round(duration_ms, 2),
            "error": error,
        }
        path = Path(settings.llm_trace_path).expanduser()

        try:
            async with self._trace_lock:
                await asyncio.to_thread(self._append_trace_record, path, record)
        except Exception:
            # Trace-file problems must not interrupt an incident investigation.
            logger.exception("Could not write Nemotron trace to %s", path)

    @staticmethod
    def _append_trace_record(path: Path, record: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as trace_file:
            trace_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

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
