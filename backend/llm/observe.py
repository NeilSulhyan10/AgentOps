"""
Record every real LLM call: what was sent, what came back, how long it took.

Two destinations, both fed from the one place that calls the LLM (``_ask_llm``):

1. The flow log (always): an ``llm_call`` event with the prompt and the raw
   answer (truncated).  The dashboard's Flow tab shows it inside the step that
   made the call, which is how you see *why* an answer was unusable.
2. Langfuse (optional): set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY, and
   LANGFUSE_HOST (https://cloud.langfuse.com for the EU cloud, https://us.cloud.langfuse.com
   for the US cloud, or your own server).  One Langfuse trace per investigation,
   one generation per LLM call.  Uses the OpenTelemetry-based SDK (4.x and later):
   Langfuse Cloud stopped accepting the older SDK's ingestion API on 2026-11-16.
   Prompts contain incident logs, so decide deliberately between cloud and self-hosting.

Calls made in rules mode are skipped by the provider and are not recorded:
there is no prompt to show.  Nothing here may ever break an investigation.
"""

import logging
from typing import Optional

from backend.config import settings
from backend.flow.log import log_flow
from backend.llm.base import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)

PROMPT_LIMIT = 8000       # characters kept in the flow log
ANSWER_LIMIT = 4000

_client = None
_client_failed = False


def _langfuse():
    """The Langfuse client, or None when it is not configured or unavailable."""
    global _client, _client_failed
    if _client or _client_failed or not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return _client
    try:
        from langfuse import Langfuse
        _client = Langfuse(public_key=settings.langfuse_public_key, secret_key=settings.langfuse_secret_key,
                           host=settings.langfuse_host)
    except Exception as exc:     # missing package, bad config: carry on without it
        _client_failed = True
        logger.warning("Langfuse disabled: %s", exc)
    return _client


def _send_to_langfuse(client, investigation_id: str, task: str, agent: str, request: LLMRequest,
                      response: LLMResponse, duration_ms: int) -> None:
    """One generation per call, all calls of an investigation in one trace and one session."""
    from langfuse import propagate_attributes

    trace_id = client.create_trace_id(seed=investigation_id)      # same investigation -> same trace
    with propagate_attributes(session_id=investigation_id, trace_name="investigation", tags=["agentops"]):
        generation = client.start_observation(
            trace_context={"trace_id": trace_id}, name=f"{task}{':' + agent if agent else ''}", as_type="generation",
            model=response.model or None,
            input=[{"role": "system", "content": request.system_prompt or ""}, {"role": "user", "content": request.prompt}],
            output=response.content, metadata={"task": task, "agent": agent, "duration_ms": duration_ms},
            usage_details={"total": response.tokens_used} if response.tokens_used else None,
            level="ERROR" if response.error else "DEFAULT", status_message=response.error,
        )
        generation.end()


def _cut(text: Optional[str], limit: int) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit] + f"… [{len(text) - limit} more characters]"


def record_call(investigation_id: str, task: str, agent: str, request: LLMRequest,
                response: LLMResponse, duration_ms: int) -> None:
    """Record one LLM call (skipped calls, i.e. rules mode, are ignored)."""
    if response.skipped:
        return
    try:
        log_flow(
            investigation_id, "llm_call", task=task, agent=agent, model=response.model,
            tokens=response.tokens_used, duration_ms=duration_ms,
            system_prompt=_cut(request.system_prompt, 1500),
            prompt=_cut(request.prompt, PROMPT_LIMIT),
            response=_cut(response.content, ANSWER_LIMIT), error=response.error,
        )
        client = _langfuse()
        if client and investigation_id:
            _send_to_langfuse(client, investigation_id, task, agent, request, response, duration_ms)
    except Exception as exc:
        logger.warning("Could not record LLM call: %s", exc)


def flush() -> None:
    """Send buffered Langfuse events (called when an investigation ends)."""
    if _client:
        try:
            _client.flush()
        except Exception as exc:
            logger.warning("Langfuse flush failed: %s", exc)
