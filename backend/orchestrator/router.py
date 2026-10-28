"""
Deterministic Router (fallback)

Used when the LLM router returns an agent name that is not in the available
pool.  Works entirely with plain strings so it handles both built-in agents
and dynamically discovered ones.
"""

from typing import List, Optional, Tuple
from backend.models import (
    InvestigationState,
    HypothesisType,
    RoutingDecision,
)

# Map evidence gap names → preferred agent name (md file stem)
_GAP_AGENT_MAP: dict[str, str] = {
    "deployment_details": "cicd_analyzer",
    "configuration_changes": "cicd_analyzer",
    "pod_memory_status": "kubernetes_analyzer",
    "pod_restart_pattern": "kubernetes_analyzer",
    "resource_pressure": "kubernetes_analyzer",
    "observability_metrics": "observability_analyzer",
    "error_patterns": "observability_analyzer",
    "trace_analysis": "observability_analyzer",
    "dependency_health": "dependency_analyzer",
    "traffic_pattern": "traffic_analyzer",
}

# Map hypothesis → preferred agent name
_HYPOTHESIS_AGENT_MAP: dict[HypothesisType, str] = {
    HypothesisType.DEPLOYMENT_INDUCED_FAILURE: "cicd_analyzer",
    HypothesisType.KUBERNETES_OOM: "kubernetes_analyzer",
    HypothesisType.TRAFFIC_INCIDENT: "observability_analyzer",
    HypothesisType.APPLICATION_ERROR: "observability_analyzer",
    HypothesisType.CONFIGURATION_ERROR: "config_analyzer",
    HypothesisType.DEPENDENCY_ISSUE: "dependency_analyzer",
}


def select_next_agent(
    investigation: InvestigationState,
    available_agents: List[str],
) -> Tuple[str, str]:
    """
    Deterministic agent selection used as LLM-router fallback.

    Parameters
    ----------
    investigation:
        Current investigation state.
    available_agents:
        List of agent name strings that may be selected (md file stems,
        e.g. "cicd_analyzer").  Must be non-empty.

    Returns
    -------
    (selected_agent_name, reasoning)
    """
    if not available_agents:
        raise ValueError("available_agents must be non-empty")

    agents_invoked: List[str] = investigation.agents_invoked
    evidence_gaps: List[str] = investigation.evidence_gaps
    current_hypothesis = investigation.current_hypothesis

    selected = available_agents[0]
    reasoning = f"Default selection: {selected}"

    # 1. Evidence-gap based selection
    for gap in evidence_gaps:
        preferred = _GAP_AGENT_MAP.get(gap)
        if preferred and preferred in available_agents:
            selected = preferred
            reasoning = f"Evidence gap '{gap}' maps to {preferred}"
            break

    # 2. Hypothesis-based override
    if current_hypothesis:
        preferred = _HYPOTHESIS_AGENT_MAP.get(current_hypothesis)
        if preferred and preferred in available_agents:
            selected = preferred
            reasoning = (
                f"Hypothesis '{current_hypothesis}' maps to {preferred}"
            )

    # 3. Recent findings hint
    for finding in reversed(investigation.agent_findings[-2:]):
        hint = _HYPOTHESIS_AGENT_MAP.get(finding.hypothesis)
        if hint and hint in available_agents:
            selected = hint
            reasoning = (
                f"Recent finding suggests {finding.hypothesis}; "
                f"routing to {hint}"
            )
            break

    # 4. A pending critic challenge outranks everything else
    if investigation.critic_reviews:
        last = investigation.critic_reviews[-1]
        if last.verdict == "challenged" and last.suggested_agent in available_agents:
            selected = last.suggested_agent
            reasoning = f"Critic challenged the conclusion and suggested {selected}"

    return selected, reasoning


def create_routing_decision(
    investigation: InvestigationState,
    selected_agent: str,
    reasoning: str,
    available_agents: List[str],
) -> RoutingDecision:
    return RoutingDecision(
        investigation_id=investigation.investigation_id,
        iteration=investigation.iteration_count,
        current_hypothesis=investigation.current_hypothesis,
        evidence_gaps=investigation.evidence_gaps,
        agents_invoked=investigation.agents_invoked,
        available_agents=available_agents,
        selected_agent=selected_agent,
        reasoning=reasoning,
    )
