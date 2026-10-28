from typing import Optional, List
import asyncio
import logging

from backend.models import (
    Incident,
    InvestigationState,
    InvestigationStatus,
    Evidence,
)
from backend.orchestrator import (
    build_investigation_graph,
    create_initial_state,
)
from backend.orchestrator.state import mongo_state_manager
from backend.config import settings
from backend.tools.data_access import get_cicd_evidence_from_github
from backend.events import (
    broadcast_status_change,
    broadcast_progress,
    broadcast_routing_decision,
    broadcast_agent_finding,
)

logger = logging.getLogger(__name__)


class InvestigationService:
    def __init__(self):
        self.graph = build_investigation_graph()

    async def start_investigation(
        self,
        incident: Incident,
        max_iterations: int = 5,
        evidence: Optional[List[Evidence]] = None,
    ) -> InvestigationState:
        """
        Create the investigation record immediately (status=PENDING) and fire the
        graph execution as a background task.  Returns the PENDING state so the
        API can respond instantly.
        """
        # --- gather evidence ---
        if evidence is not None:
            github_evidence = evidence
            logger.info(f"Using {len(github_evidence)} provided evidence items for {incident.incident_id}")
        else:
            if not settings.github_token:
                raise ValueError("GITHUB_TOKEN is required.")
            if not settings.github_owner:
                raise ValueError("GITHUB_OWNER is required.")
            if not settings.github_repo:
                raise ValueError("GITHUB_REPO is required.")
            logger.info(f"Fetching CI/CD evidence from GitHub Actions for {incident.incident_id}")
            github_evidence = await get_cicd_evidence_from_github(incident)
            logger.info(f"Loaded {len(github_evidence)} evidence items from GitHub Actions")

        # --- persist initial PENDING state ---
        initial_state = await mongo_state_manager.create_state(
            incident, max_iterations, evidence=github_evidence
        )

        # --- fire graph in background, return immediately ---
        asyncio.create_task(
            self._run_investigation(initial_state, max_iterations),
            name=f"investigation-{initial_state.investigation_id}",
        )

        return initial_state

    async def _run_investigation(
        self, initial_state: InvestigationState, max_iterations: int
    ) -> None:
        """Background task: run the graph and persist state at each step."""
        investigation_id = initial_state.investigation_id

        await broadcast_status_change(investigation_id, "running")
        await broadcast_progress(investigation_id, 0, max_iterations, 0.0)

        graph_input = {
            "investigation": initial_state,
            "messages": [],
            "current_agent": None,
            "should_continue": True,
            "next_action": "normalize",
        }

        config = {"recursion_limit": 50}
        final_state = {"investigation": initial_state}

        try:
            async for event in self.graph.astream(graph_input, config=config):
                for node_name, state_update in event.items():
                    investigation = state_update.get("investigation")
                    if not investigation:
                        continue

                    final_state["investigation"] = investigation

                    # Persist after every node so the status is always current in DB
                    try:
                        await mongo_state_manager.update_state(investigation)
                    except Exception as e:
                        logger.warning(f"State update failed at node '{node_name}': {e}")

                    iteration = investigation.iteration_count
                    await broadcast_progress(
                        investigation_id,
                        iteration,
                        investigation.max_iterations,
                        investigation.overall_confidence,
                    )

                    if node_name == "route" and investigation.routing_decisions:
                        d = investigation.routing_decisions[-1]
                        agent = d.selected_agent if isinstance(d.selected_agent, str) else d.selected_agent.value
                        await broadcast_routing_decision(investigation_id, agent, d.reasoning, iteration)

                    elif node_name == "critique" and investigation.critic_reviews:
                        r = investigation.critic_reviews[-1]
                        await broadcast_agent_finding(investigation_id, "critic", {
                            "hypothesis": r.assessed_hypothesis if isinstance(r.assessed_hypothesis, str) else r.assessed_hypothesis.value,
                            "finding": f"{r.verdict}: " + ("; ".join(r.concerns) or "conclusion corroborated"),
                            "confidence": r.confidence,
                            "reasoning": r.reasoning,
                            "evidence": [],
                        })

                    elif node_name == "invoke_agent" and investigation.agent_findings:
                        f = investigation.agent_findings[-1]
                        await broadcast_agent_finding(investigation_id, f.agent_type, {
                            "hypothesis": f.hypothesis if isinstance(f.hypothesis, str) else f.hypothesis.value,
                            "finding": f.finding,
                            "confidence": f.confidence,
                            "reasoning": f.reasoning,
                            "evidence": f.evidence,
                        })

        except Exception as e:
            logger.error(f"Graph execution failed for {investigation_id}: {e}", exc_info=True)
            inv = final_state["investigation"]
            inv.investigation_status = InvestigationStatus.FAILED
            try:
                await mongo_state_manager.update_state(inv)
            except Exception:
                pass
            await broadcast_status_change(investigation_id, InvestigationStatus.FAILED)
            return

        completed = final_state["investigation"]
        status_str = (
            completed.investigation_status
            if isinstance(completed.investigation_status, str)
            else completed.investigation_status.value
        )
        await broadcast_status_change(investigation_id, status_str)
        logger.info(f"Investigation {investigation_id} finished: {status_str}")

    async def get_investigation(self, investigation_id: str) -> Optional[InvestigationState]:
        return await mongo_state_manager.get_state(investigation_id)

    async def list_investigations(
        self, status: Optional[InvestigationStatus] = None
    ) -> List[InvestigationState]:
        return await mongo_state_manager.list_states_lite(status)


investigation_service = InvestigationService()
