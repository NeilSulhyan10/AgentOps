from typing import Optional, List
from backend.models import (
    Incident,
    InvestigationState,
    InvestigationStatus,
    AgentType,
    Evidence,
)
from backend.orchestrator import (
    build_investigation_graph,
    create_initial_state,
)
from backend.orchestrator.state import mongo_state_manager
from backend.config import settings
from backend.tools.data_access import get_cicd_evidence_from_github

import logging
logger = logging.getLogger(__name__)


class InvestigationService:
    def __init__(self):
        self.graph = build_investigation_graph()

    async def start_investigation(self, incident: Incident, max_iterations: int = 5, evidence: Optional[List[Evidence]] = None) -> InvestigationState:
        # Validate GitHub configuration is present
        if not settings.github_token:
            raise ValueError("GITHUB_TOKEN is required but not configured. Please set GITHUB_TOKEN in environment.")
        if not settings.github_owner:
            raise ValueError("GITHUB_OWNER is required but not configured. Please set GITHUB_OWNER in environment.")
        if not settings.github_repo:
            raise ValueError("GITHUB_REPO is required but not configured. Please set GITHUB_REPO in environment.")

        # Use provided evidence or fetch from GitHub Actions
        if evidence is not None:
            github_evidence = evidence
            logger.info(f"Using provided {len(github_evidence)} evidence items for incident {incident.incident_id}")
        else:
            # Fetch CI/CD evidence from GitHub Actions BEFORE creating state
            logger.info(f"Fetching CI/CD evidence from GitHub Actions for incident {incident.incident_id}")
            github_evidence = await get_cicd_evidence_from_github(incident)
            logger.info(f"Loaded {len(github_evidence)} evidence items from GitHub Actions")

        # Use state manager to create state with evidence (which creates IncidentDoc in MongoDB)
        initial_state = await mongo_state_manager.create_state(incident, max_iterations, evidence=github_evidence)

        graph_input = {
            "investigation": initial_state,
            "messages": [],
            "current_agent": None,
            "should_continue": True,
            "next_action": "normalize"
        }

        logger.info(f"Starting graph execution for investigation {initial_state.investigation_id}")
        result = await self.graph.ainvoke(graph_input)
        logger.info(f"Graph execution completed for investigation {initial_state.investigation_id}")
        final_state = result["investigation"]
        await mongo_state_manager.update_state(final_state)

        return final_state

    async def get_investigation(self, investigation_id: str) -> Optional[InvestigationState]:
        return await mongo_state_manager.get_state(investigation_id)

    async def list_investigations(self, status: Optional[InvestigationStatus] = None) -> List[InvestigationState]:
        return await mongo_state_manager.list_states(status)


investigation_service = InvestigationService()