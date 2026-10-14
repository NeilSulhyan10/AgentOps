from typing import Dict, List, Any, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
import asyncio

from backend.models import (
    InvestigationState,
    Incident,
    Evidence,
    AgentFinding,
    RoutingDecision,
    ConfidenceEntry,
    RootCauseAnalysis,
    RemediationRecommendation,
    AgentType,
    HypothesisType,
    InvestigationStatus,
    EvidenceType
)
from backend.tools.data_access import get_cicd_evidence, get_kubernetes_evidence, get_observability_evidence
from backend.runtime import get_agent_runner
from backend.orchestrator.router import select_next_agent
from backend.events import broadcast_agent_thinking


class GraphState(TypedDict):
    investigation: InvestigationState
    messages: Annotated[List[Any], add_messages]
    current_agent: Optional[AgentType]
    should_continue: bool
    next_action: str


def create_initial_state(incident: Incident, max_iterations: int = 5) -> InvestigationState:
    return InvestigationState(
        incident=incident,
        incident_id=incident.incident_id,
        max_iterations=max_iterations,
        investigation_status=InvestigationStatus.PENDING
    )


def normalize_incident(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    investigation.investigation_status = InvestigationStatus.RUNNING
    investigation.updated_at = investigation.updated_at
    import logging
    logging.getLogger(__name__).info(f"normalize_incident: investigation {investigation.investigation_id}")
    return {"investigation": investigation, "next_action": "pre_filter"}


def rule_based_pre_filter(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    incident = investigation.incident

    evidence_gaps = []
    initial_hypothesis = HypothesisType.UNKNOWN

    description = incident.description.lower()
    title = incident.title.lower()

    if any(kw in description or kw in title for kw in ["deployment", "deploy", "rollout", "canary", "release"]):
        evidence_gaps.append("deployment_details")
        initial_hypothesis = HypothesisType.DEPLOYMENT_INDUCED_FAILURE

    if any(kw in description or kw in title for kw in ["oom", "memory", "killed", "exit code 137", "137", "crashloop"]):
        evidence_gaps.append("pod_memory_status")
        initial_hypothesis = HypothesisType.KUBERNETES_OOM

    if any(kw in description or kw in title for kw in ["latency", "slow", "timeout", "p99", "p95", "5xx", "error rate", "errors"]):
        evidence_gaps.append("observability_metrics")
        if initial_hypothesis == HypothesisType.UNKNOWN:
            initial_hypothesis = HypothesisType.TRAFFIC_INCIDENT

    if any(kw in description or kw in title for kw in ["config", "configuration", "env", "environment variable"]):
        evidence_gaps.append("configuration_changes")
        if initial_hypothesis == HypothesisType.UNKNOWN:
            initial_hypothesis = HypothesisType.CONFIGURATION_ERROR

    investigation.current_hypothesis = initial_hypothesis
    investigation.evidence_gaps = evidence_gaps
    investigation.updated_at = investigation.updated_at
    import logging
    logging.getLogger(__name__).info(f"rule_based_pre_filter: investigation {investigation.investigation_id}, hypothesis={initial_hypothesis}, gaps={evidence_gaps}")

    return {"investigation": investigation, "next_action": "load_evidence"}


def load_evidence(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    import logging
    logging.getLogger(__name__).info(f"load_evidence: investigation {investigation.investigation_id}, existing_evidence={len(investigation.evidence)}")
    
    has_github_evidence = any(
        ev.source in ("github_actions", "github_actions_job_logs") 
        for ev in investigation.evidence
    )
    
    if not has_github_evidence:
        cicd_evidence = get_cicd_evidence(investigation.incident)
        investigation.evidence.extend(cicd_evidence)
    
    k8s_evidence = get_kubernetes_evidence(investigation.incident)
    obs_evidence = get_observability_evidence(investigation.incident)
    
    investigation.evidence.extend(k8s_evidence)
    investigation.evidence.extend(obs_evidence)
    investigation.updated_at = investigation.updated_at
    logging.getLogger(__name__).info(f"load_evidence: investigation {investigation.investigation_id}, total_evidence={len(investigation.evidence)}")
    
    return {"investigation": investigation, "next_action": "route"}


def _format_evidence_summary(evidence: list) -> str:
    if not evidence:
        return "No evidence collected yet."
    lines = []
    for ev in evidence[-10:]:
        lines.append(f"  - evidence_id={ev.evidence_id} [{ev.agent_type}] {ev.evidence_type}: {ev.description[:200]}")
    return "\n".join(lines)


def _format_findings_summary(findings: list) -> str:
    if not findings:
        return "No agent findings yet."
    lines = []
    for f in findings[-5:]:
        lines.append(f"  - [{f.agent_type}] {f.hypothesis}: {f.finding[:100]} (confidence: {f.confidence:.2f})")
    return "\n".join(lines)


async def adaptive_router(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    import logging
    logging.getLogger(__name__).info(f"adaptive_router: investigation {investigation.investigation_id}, iteration={investigation.iteration_count}")

    if investigation.iteration_count >= investigation.max_iterations:
        investigation.investigation_status = InvestigationStatus.MAX_ITERATIONS_REACHED
        return {"investigation": investigation, "next_action": "finalize", "should_continue": False}

    agents_invoked = investigation.agents_invoked
    evidence_gaps = investigation.evidence_gaps
    current_hypothesis = investigation.current_hypothesis

    available_agents = [a for a in AgentType if a not in agents_invoked]
    if not available_agents:
        available_agents = list(AgentType)

    runner = await get_agent_runner()
    
    evidence_summary = _format_evidence_summary(investigation.evidence)
    findings_summary = _format_findings_summary(investigation.agent_findings)
    
    selected_agent, reasoning = await runner.run_router_agent(
        incident=investigation.incident,
        current_hypothesis=current_hypothesis,
        evidence_gaps=evidence_gaps,
        agents_invoked=agents_invoked,
        available_agents=available_agents,
        evidence_summary=evidence_summary,
        findings_summary=findings_summary
    )

    if selected_agent not in available_agents:
        selected_agent, _ = select_next_agent(investigation)
        if selected_agent not in available_agents:
            selected_agent = available_agents[0]
        reasoning = f"Router selected an unavailable agent; deterministic fallback selected {selected_agent}"

    decision = RoutingDecision(
        investigation_id=investigation.investigation_id,
        iteration=investigation.iteration_count,
        current_hypothesis=current_hypothesis,
        evidence_gaps=evidence_gaps,
        agents_invoked=agents_invoked,
        available_agents=available_agents,
        selected_agent=selected_agent,
        reasoning=reasoning
    )
    investigation.routing_decisions.append(decision)
    investigation.iteration_count += 1
    investigation.updated_at = investigation.updated_at
    logging.getLogger(__name__).info(f"adaptive_router: investigation {investigation.investigation_id}, selected_agent={selected_agent}, reasoning={reasoning}")

    return {
        "investigation": investigation,
        "current_agent": selected_agent,
        "next_action": "invoke_agent",
        "should_continue": True
    }


async def invoke_cicd_agent(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    return await _invoke_analysis_agent(investigation, "cicd_analyzer", AgentType.CICD)


async def invoke_kubernetes_agent(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    return await _invoke_analysis_agent(investigation, "kubernetes_analyzer", AgentType.KUBERNETES)


async def invoke_observability_agent(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    return await _invoke_analysis_agent(investigation, "observability_analyzer", AgentType.OBSERVABILITY)


async def _invoke_analysis_agent(investigation: InvestigationState, agent_name: str, agent_type: AgentType) -> GraphState:
    import logging
    logging.getLogger(__name__).info(f"_invoke_analysis_agent: investigation {investigation.investigation_id}, agent_name={agent_name}")

    runner = await get_agent_runner()
    
    await broadcast_agent_thinking(investigation.investigation_id, agent_type.value, "started")
    try:
        finding = await runner.run_analysis_agent(
            agent_name=agent_name,
            incident=investigation.incident,
            evidence=investigation.evidence,
            previous_findings=investigation.agent_findings
        )
    except Exception:
        await broadcast_agent_thinking(investigation.investigation_id, agent_type.value, "failed")
        raise
    
    finding.investigation_id = investigation.investigation_id
    finding.iteration = investigation.iteration_count
    
    investigation.agent_findings.append(finding)
    investigation.agents_invoked.append(agent_type)
    investigation.updated_at = investigation.updated_at
    logging.getLogger(__name__).info(f"_invoke_analysis_agent: investigation {investigation.investigation_id}, agent_type={agent_type}, finding={finding.finding[:100]}")

    matching_evidence = [item for item in investigation.evidence if item.evidence_id in finding.evidence]
    investigation.confidence_scores[agent_type] = finding.confidence if matching_evidence else 0.0
    gap_evidence_types = {
        "deployment_details": {EvidenceType.DEPLOYMENT, EvidenceType.CODE_CHANGE, EvidenceType.JOB_FAILURE},
        "configuration_changes": {EvidenceType.CONFIG_CHANGE},
        "pod_memory_status": {EvidenceType.POD_EXIT_CODE, EvidenceType.RESOURCE_USAGE, EvidenceType.RESOURCE_LIMIT, EvidenceType.POD_EVENT},
        "pod_restart_pattern": {EvidenceType.POD_RESTART_COUNT, EvidenceType.POD_EVENT},
        "resource_pressure": {EvidenceType.RESOURCE_USAGE, EvidenceType.RESOURCE_LIMIT},
        "observability_metrics": {EvidenceType.LATENCY, EvidenceType.ERROR_RATE},
        "error_patterns": {EvidenceType.LOG, EvidenceType.STACK_TRACE, EvidenceType.ERROR_STATUS},
        "trace_analysis": {EvidenceType.TRACE, EvidenceType.SPAN_DURATION},
    }
    resolved_gaps = {
        gap for gap in investigation.evidence_gaps
        if gap in gap_evidence_types
        and any(item.evidence_type in gap_evidence_types[gap] for item in matching_evidence)
    }
    investigation.evidence_gaps = [gap for gap in investigation.evidence_gaps if gap not in resolved_gaps]
    await broadcast_agent_thinking(investigation.investigation_id, agent_type.value, "completed")

    return {"investigation": investigation, "next_action": "evaluate"}


def evaluate_evidence(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    return _evaluate_evidence(investigation)


def _evaluate_evidence(investigation: InvestigationState) -> GraphState:
    from backend.orchestrator.confidence import calculate_overall_confidence
    from backend.config import settings

    evidence_ids = {item.evidence_id for item in investigation.evidence}
    grounded_confidences = {
        finding.agent_type: finding.confidence
        for finding in investigation.agent_findings
        if finding.evidence and any(reference in evidence_ids for reference in finding.evidence)
    }
    overall_confidence = calculate_overall_confidence(grounded_confidences)
    investigation.overall_confidence = overall_confidence

    entry = ConfidenceEntry(
        investigation_id=investigation.investigation_id,
        iteration=investigation.iteration_count,
        agent_confidences=grounded_confidences.copy(),
        overall_confidence=overall_confidence,
        threshold=settings.confidence_threshold,
        is_sufficient=overall_confidence >= settings.confidence_threshold
    )
    investigation.confidence_history.append(entry)
    investigation.updated_at = investigation.updated_at

    if overall_confidence >= settings.confidence_threshold:
        investigation.investigation_status = InvestigationStatus.COMPLETED
        return {"investigation": investigation, "next_action": "generate_rca", "should_continue": False}
    elif investigation.iteration_count >= investigation.max_iterations:
        investigation.investigation_status = InvestigationStatus.MAX_ITERATIONS_REACHED
        return {"investigation": investigation, "next_action": "generate_rca", "should_continue": False}
    else:
        return {"investigation": investigation, "next_action": "route", "should_continue": True}


async def generate_rca(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    return await _generate_rca(investigation)


async def _generate_rca(investigation: InvestigationState) -> GraphState:
    runner = await get_agent_runner()
    
    rca = await runner.run_rca_agent(
        incident=investigation.incident,
        agent_findings=investigation.agent_findings,
        evidence=investigation.evidence,
        routing_decisions=investigation.routing_decisions,
        confidence_history=investigation.confidence_history
    )
    
    rca.investigation_id = investigation.investigation_id
    investigation.root_cause = rca

    remediation = await runner.run_remediation_agent(
        root_cause=rca.root_cause if rca else "Unknown",
        root_cause_type=rca.root_cause_type if rca else HypothesisType.UNKNOWN,
        confidence=investigation.overall_confidence
    )
    
    remediation.investigation_id = investigation.investigation_id
    remediation.rca_id = rca.rca_id if rca else ""
    investigation.remediation = remediation

    if investigation.investigation_status not in (
        InvestigationStatus.MAX_ITERATIONS_REACHED,
        InvestigationStatus.INSUFFICIENT_EVIDENCE,
    ):
        investigation.investigation_status = InvestigationStatus.COMPLETED
    investigation.completed_at = investigation.updated_at
    investigation.updated_at = investigation.updated_at

    return {"investigation": investigation, "next_action": "persist", "should_continue": False}


async def persist_investigation(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    investigation.updated_at = investigation.updated_at
    return {"investigation": investigation, "next_action": "end"}


def _format_routing_summary(decisions: list) -> str:
    if not decisions:
        return "No routing decisions yet."
    lines = []
    for d in decisions:
        lines.append(f"  - Iteration {d.iteration}: routed to {d.selected_agent} ({d.reasoning})")
    return "\n".join(lines)


def _format_confidence_history(history: list) -> str:
    if not history:
        return "No confidence history yet."
    lines = []
    for h in history:
        agent_str = ', '.join(
            f'{k if isinstance(k, str) else k.value}:{v:.2f}' 
            for k, v in h.agent_confidences.items()
        )
        lines.append(f"  - Iteration {h.iteration}: overall={h.overall_confidence:.2f}, agents={{{agent_str}}}")
    return "\n".join(lines)


def _format_evidence_summary(evidence: list) -> str:
    if not evidence:
        return "No evidence collected yet."
    lines = []
    for ev in evidence[-10:]:
        lines.append(f"  - [{ev.agent_type}] {ev.evidence_type}: {ev.description[:100]}")
    return "\n".join(lines)


def _format_findings_summary(findings: list) -> str:
    if not findings:
        return "No agent findings yet."
    lines = []
    for f in findings[-5:]:
        lines.append(f"  - [{f.agent_type}] {f.hypothesis}: {f.finding[:100]} (confidence: {f.confidence:.2f})")
    return "\n".join(lines)


def build_investigation_graph() -> StateGraph:
    workflow = StateGraph(GraphState)

    workflow.add_node("normalize", normalize_incident)
    workflow.add_node("pre_filter", rule_based_pre_filter)
    workflow.add_node("route", adaptive_router)
    workflow.add_node("invoke_cicd", invoke_cicd_agent)
    workflow.add_node("invoke_kubernetes", invoke_kubernetes_agent)
    workflow.add_node("invoke_observability", invoke_observability_agent)
    workflow.add_node("evaluate", evaluate_evidence)
    workflow.add_node("load_evidence", load_evidence)
    workflow.add_node("generate_rca", generate_rca)
    workflow.add_node("persist", persist_investigation)

    workflow.add_edge(START, "normalize")
    workflow.add_edge("normalize", "pre_filter")
    workflow.add_edge("pre_filter", "load_evidence")
    workflow.add_edge("load_evidence", "route")

    def agent_router(state: GraphState) -> str:
        action = state.get("next_action")
        if action == "finalize" or action == "generate_rca":
            return "generate_rca"
        agent = state.get("current_agent")
        if agent == AgentType.CICD:
            return "invoke_cicd"
        elif agent == AgentType.KUBERNETES:
            return "invoke_kubernetes"
        elif agent == AgentType.OBSERVABILITY:
            return "invoke_observability"
        return "invoke_cicd"

    workflow.add_conditional_edges(
        "route",
        agent_router,
        {
            "invoke_cicd": "invoke_cicd",
            "invoke_kubernetes": "invoke_kubernetes",
            "invoke_observability": "invoke_observability",
            "generate_rca": "generate_rca"
        }
    )

    workflow.add_edge("invoke_cicd", "evaluate")
    workflow.add_edge("invoke_kubernetes", "evaluate")
    workflow.add_edge("invoke_observability", "evaluate")

    workflow.add_conditional_edges(
        "evaluate",
        lambda state: state["next_action"],
        {
            "route": "route",
            "generate_rca": "generate_rca"
        }
    )

    workflow.add_edge("generate_rca", "persist")
    workflow.add_edge("persist", END)

    return workflow.compile()
