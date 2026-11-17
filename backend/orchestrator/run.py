"""
Run one investigation through the graph, in this process.

`run_investigation` is the single entry point used by the CLI
(scripts/investigate.py) and the tests.  The API service
(backend/services/investigation_service.py) runs the same graph but also
persists to MongoDB and broadcasts progress, so it keeps its own loop.

Both write the same `investigation_started` / `investigation_finished` events
to the flow log, which is what lets a flow report show how a run ended.
"""

import time

from backend.config import settings
from backend.flow.log import log_flow
from backend.llm import get_llm_provider
from backend.models import InvestigationState, InvestigationStatus
from backend.orchestrator.graph import build_investigation_graph


def log_investigation_started(state: InvestigationState) -> None:
    incident = state.incident
    log_flow(
        state.investigation_id, "investigation_started",
        incident_id=incident.incident_id, title=incident.title, service_name=incident.service_name,
        engine=get_llm_provider().provider_name, fault=settings.fault_injection,
        max_iterations=state.max_iterations, threshold=settings.confidence_threshold,
    )


def log_investigation_finished(state: InvestigationState, started: float) -> None:
    from backend.runtime.spawner import forget
    forget(state.investigation_id)   # spawned agents belong to one run
    from backend.llm.observe import flush
    flush()                          # send buffered Langfuse events, if enabled
    status = state.investigation_status
    log_flow(
        state.investigation_id, "investigation_finished",
        status=getattr(status, "value", status), duration_ms=round((time.perf_counter() - started) * 1000),
    )


async def run_investigation(state: InvestigationState) -> InvestigationState:
    """
    Run `state` to the end and return the final state.  If a node raises, the
    returned state has status FAILED and the flow log names the failing node.
    """
    graph = build_investigation_graph()
    started = time.perf_counter()
    log_investigation_started(state)

    final = state
    try:
        result = await graph.ainvoke(
            {"investigation": state, "messages": [], "current_agent": None, "should_continue": True, "next_action": "normalize"},
            config={"recursion_limit": 50},
        )
        final = result["investigation"]
    except Exception:
        state.investigation_status = InvestigationStatus.FAILED
    log_investigation_finished(final, started)
    return final
