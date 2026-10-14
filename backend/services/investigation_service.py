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
from backend.events import (
    broadcast_status_change,
    broadcast_progress,
    broadcast_routing_decision,
    broadcast_agent_finding,
)

import logging
logger = logging.getLogger(__name__)


class InvestigationService:
    def __init__(self):
        self.graph = build_investigation_graph()

    async def start_investigation(self, incident: Incident, max_iterations: int = 5, evidence: Optional[List[Evidence]] = None) -> InvestigationState:
        # Use provided evidence or fetch from GitHub Actions
        if evidence is not None:
            github_evidence = evidence
            logger.info(f"Using provided {len(github_evidence)} evidence items for incident {incident.incident_id}")
        else:
            if not settings.github_token:
                raise ValueError("GITHUB_TOKEN is required to fetch GitHub Actions evidence.")
            if not settings.github_owner:
                raise ValueError("GITHUB_OWNER is required to fetch GitHub Actions evidence.")
            if not settings.github_repo:
                raise ValueError("GITHUB_REPO is required to fetch GitHub Actions evidence.")
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

        investigation_id = initial_state.investigation_id
        
        # Broadcast initial status
        await broadcast_status_change(investigation_id, "running")
        await broadcast_progress(investigation_id, 0, max_iterations, 0.0)

        logger.info(f"Starting graph execution for investigation {investigation_id}")
        
        # Run graph with step-by-step execution to capture events
        # We'll use a custom approach to track node execution
        result = await self._run_graph_with_events(graph_input, max_iterations)
        
        logger.info(f"Graph execution completed for investigation {investigation_id}")
        final_state = result["investigation"]
        await mongo_state_manager.update_state(final_state)

        # Broadcast completion
        await broadcast_status_change(investigation_id, final_state.investigation_status if isinstance(final_state.investigation_status, str) else final_state.investigation_status.value)
        
        return final_state

    async def _run_graph_with_events(self, graph_input: dict, max_iterations: int) -> dict:
        """Run graph step by step to capture and broadcast events."""
        from backend.orchestrator.graph import build_investigation_graph
        from backend.models import AgentType, InvestigationStatus
        import asyncio
        
        graph = build_investigation_graph()
        investigation_id = graph_input["investigation"].investigation_id
        
        # We'll use the graph's astream to get intermediate states
        config = {"recursion_limit": 50}
        final_state = {"investigation": graph_input["investigation"]}
        iteration = 0
        
        async for event in graph.astream(graph_input, config=config):
            # event is a dict with node name as key and state update as value
            for node_name, state_update in event.items():
                investigation = state_update.get("investigation")
                if not investigation:
                    continue
                final_state["investigation"] = investigation
                
                iteration = investigation.iteration_count
                
                # Broadcast progress
                await broadcast_progress(investigation.investigation_id, iteration, investigation.max_iterations, investigation.overall_confidence)
                
                # Handle node-specific events
                if node_name == "route":
                    # Router just completed, broadcast routing decision
                    if investigation.routing_decisions:
                        latest_decision = investigation.routing_decisions[-1]
                        selected_agent = latest_decision.selected_agent
                        reasoning = latest_decision.reasoning
                        if hasattr(selected_agent, 'value'):
                            selected_agent = selected_agent.value
                        await broadcast_routing_decision(investigation.investigation_id, selected_agent, reasoning, iteration)
                
                elif node_name in ("invoke_cicd", "invoke_kubernetes", "invoke_observability"):
                    # Agent is about to start or just completed
                    agent_type = node_name.replace("invoke_", "")
                    if investigation.agent_findings:
                        latest_finding = investigation.agent_findings[-1]
                        if latest_finding.agent_type == agent_type or (hasattr(latest_finding.agent_type, 'value') and latest_finding.agent_type.value == agent_type):
                            # Agent just completed, broadcast finding
                            finding_data = {
                                "hypothesis": latest_finding.hypothesis.value if hasattr(latest_finding.hypothesis, 'value') else str(latest_finding.hypothesis),
                                "finding": latest_finding.finding,
                                "confidence": latest_finding.confidence,
                                "reasoning": latest_finding.reasoning,
                                "evidence": latest_finding.evidence
                            }
                            await broadcast_agent_finding(investigation.investigation_id, agent_type, finding_data)
                
                elif node_name == "evaluate":
                    # Evaluation completed, broadcast progress
                    await broadcast_progress(investigation.investigation_id, iteration, investigation.max_iterations, investigation.overall_confidence)
        
        # astream already executed the graph; ainvoke here would run agents again.
        return final_state

    async def get_investigation(self, investigation_id: str) -> Optional[InvestigationState]:
        return await mongo_state_manager.get_state(investigation_id)

    async def list_investigations(self, status: Optional[InvestigationStatus] = None) -> List[InvestigationState]:
        # Use lite version for better performance - doesn't load all related data
        return await mongo_state_manager.list_states_lite(status)


investigation_service = InvestigationService()
