"""
Investigation flow logger.

Appends one JSON object per line to ``settings.flow_log_path`` so that the
path of an investigation (routing, agents used, confidence, fallbacks) can be
analysed afterwards. See ``scripts/analyze_flow.py`` for a summary tool.
"""

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()


def _jsonable(value: Any) -> Any:
    return value.value if hasattr(value, "value") else str(value)


def log_flow(investigation_id: str, event: str, **fields: Any) -> None:
    """Record a flow event. Never raises — logging must not break an investigation."""
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
