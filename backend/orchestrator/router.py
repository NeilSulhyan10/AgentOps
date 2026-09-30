from typing import List, Optional
from backend.models import (
    InvestigationState,
    AgentType,
    HypothesisType,
    RoutingDecision,
    Evidence
)


def select_next_agent(investigation: InvestigationState) -> tuple[AgentType, str]:
    agents_invoked = investigation.agents_invoked
    evidence_gaps = investigation.evidence_gaps
    current_hypothesis = investigation.current_hypothesis
    available_agents = [a for a in AgentType if a not in agents_invoked]

    if not available_agents:
        available_agents = list(AgentType)

    selected_agent = available_agents[0]
    selected_agent_str = selected_agent if isinstance(selected_agent, AgentType) else selected_agent
    reasoning = f"Default selection: {selected_agent_str}"

    gap_agent_map = {
        "deployment_details": AgentType.CICD,
        "configuration_changes": AgentType.CICD,
        "pod_memory_status": AgentType.KUBERNETES,
        "pod_restart_pattern": AgentType.KUBERNETES,
        "resource_pressure": AgentType.KUBERNETES,
        "observability_metrics": AgentType.OBSERVABILITY,
        "error_patterns": AgentType.OBSERVABILITY,
        "trace_analysis": AgentType.OBSERVABILITY
    }

    for gap in evidence_gaps:
        if gap in gap_agent_map and gap_agent_map[gap] in available_agents:
            selected_agent = gap_agent_map[gap]
            selected_agent_str = selected_agent if isinstance(selected_agent, AgentType) else selected_agent
            reasoning = f"Evidence gap '{gap}' maps to {selected_agent_str} agent"
            break

    if current_hypothesis == HypothesisType.DEPLOYMENT_INDUCED_FAILURE and AgentType.CICD in available_agents:
        selected_agent = AgentType.CICD
        reasoning = "Hypothesis suggests deployment-induced failure, prioritizing CI/CD agent"
    elif current_hypothesis == HypothesisType.KUBERNETES_OOM and AgentType.KUBERNETES in available_agents:
        selected_agent = AgentType.KUBERNETES
        reasoning = "Hypothesis suggests Kubernetes OOM, prioritizing Kubernetes agent"
    elif current_hypothesis == HypothesisType.TRAFFIC_INCIDENT and AgentType.OBSERVABILITY in available_agents:
        selected_agent = AgentType.OBSERVABILITY
        reasoning = "Hypothesis suggests traffic incident, prioritizing Observability agent"

    recent_findings = investigation.agent_findings[-2:] if investigation.agent_findings else []
    for finding in recent_findings:
        if finding.hypothesis == HypothesisType.KUBERNETES_OOM and AgentType.KUBERNETES in available_agents:
            selected_agent = AgentType.KUBERNETES
            reasoning = "Previous finding suggests Kubernetes issue, investigating further"
            break
        elif finding.hypothesis == HypothesisType.DEPLOYMENT_INDUCED_FAILURE and AgentType.CICD in available_agents:
            selected_agent = AgentType.CICD
            reasoning = "Previous finding suggests deployment issue, investigating further"
            break

    return selected_agent, reasoning


def create_routing_decision(
    investigation: InvestigationState,
    selected_agent: AgentType,
    reasoning: str
) -> RoutingDecision:
    return RoutingDecision(
        investigation_id=investigation.investigation_id,
        iteration=investigation.iteration_count,
        current_hypothesis=investigation.current_hypothesis,
        evidence_gaps=investigation.evidence_gaps,
        agents_invoked=investigation.agents_invoked,
        available_agents=[a for a in AgentType if a not in investigation.agents_invoked] or list(AgentType),
        selected_agent=selected_agent,
        reasoning=reasoning
    )