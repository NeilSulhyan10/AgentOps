"""
Flow log: one JSON line per thing that happens during an investigation.

Writing:  ``log_flow(investigation_id, "route", selected_agent="cicd_analyzer", ...)``
Reading:  ``read_events()`` returns every event; ``read_events(investigation_id)`` one run.

The file lives at ``settings.flow_log_path`` (default ``logs/flow.jsonl``).
It is the single source for flow reports and diagrams (``backend/flow/trace.py``).

Events and who writes them
--------------------------
investigation_started   run_investigation       incident, engine, injected fault
pre_filter              pre_filter node         first-guess hypothesis, evidence gaps
load_evidence           load_evidence node      evidence count and sources
llm_call                agent runner            prompt, raw answer, tokens, time of one real LLM call
llm_parse_fallback      agent runner            an LLM answer was unusable; rules took over
route                   route node              selected agent, LLM choice, fallback flag
route_stopped           route node              max_iterations reached
agent_finding           invoke_agent node       hypothesis, confidence, grounded evidence
evaluate                evaluate node           overall confidence vs threshold
critic                  critique node           verdict, concerns, whether it looped back
rca                     generate_rca node       root-cause type, final confidence
node_failed             any node (wrapper)      node name and the exception
investigation_finished  run_investigation       final status
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from backend.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _jsonable(value: Any) -> Any:
    return value.value if hasattr(value, "value") else str(value)


def log_flow(investigation_id: str, event: str, **fields: Any) -> None:
    """Record a flow event. Never raises: logging must not break an investigation."""
    if not settings.flow_log_enabled:
        return
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "investigation_id": investigation_id,
        "event": event,
        **fields,
    }
    try:
        path = Path(settings.flow_log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, default=_jsonable)
        with _lock, path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        logger.exception("Could not write flow log to %s", settings.flow_log_path)


def read_events(investigation_id: Optional[str] = None, path: Optional[str] = None) -> List[dict]:
    """Read flow events, oldest first. Unreadable lines are skipped, not fatal."""
    log_path = Path(path or settings.flow_log_path)
    if not log_path.exists():
        return []
    events = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if investigation_id is None or event.get("investigation_id") == investigation_id:
            events.append(event)
    return events
