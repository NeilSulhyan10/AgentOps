from typing import Optional, List
from backend.models import (
    Incident,
    InvestigationState,
    InvestigationStatus,
    AgentType
)
from backend.orchestrator import (
    build_investigation_graph,
    create_initial_state,
)
from backend.orchestrator.state import mongo_state_manager


class InvestigationService:
    def __init__(self):
        self.graph = build_investigation_graph()

    async def start_investigation(self, incident: Incident, max_iterations: int = 5) -> InvestigationState:
        initial_state = create_initial_state(incident, max_iterations)

        graph_input = {
            "investigation": initial_state,
            "messages": [],
            "current_agent": None,
            "should_continue": True,
            "next_action": "normalize"
        }

        result = await self.graph.ainvoke(graph_input)
        final_state = result["investigation"]
        await mongo_state_manager.update_state(final_state)

        return final_state

    async def get_investigation(self, investigation_id: str) -> Optional[InvestigationState]:
        return await mongo_state_manager.get_state(investigation_id)

    async def list_investigations(self, status: Optional[InvestigationStatus] = None) -> List[InvestigationState]:
        return await mongo_state_manager.list_states(status)


investigation_service = InvestigationService()