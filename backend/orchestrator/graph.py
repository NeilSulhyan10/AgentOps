"""
Investigation Graph

Builds a LangGraph StateGraph that drives the investigation pipeline.

Key design: a single generic `invoke_agent` node handles ALL specialist agents.
The router writes the chosen agent name (a plain string matching a .md filename
stem) into GraphState["current_agent"].  Adding a new specialist agent requires
only dropping a .md file into agents/markdown/ — no code changes.
"""

from typing import Dict, List, Any, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
import logging
import time

from backend.models import (
    InvestigationState,
    Incident,
    Evidence,
    AgentFinding,
    RoutingDecision,
    ConfidenceEntry,
    RootCauseAnalysis,
    RemediationRecommendation,
    HypothesisType,
    InvestigationStatus,
    EvidenceType,
)
from backend.tools.data_access import get_cicd_evidence, get_kubernetes_evidence, get_observability_evidence
from backend.runtime import get_agent_runner
from backend.orchestrator.router import select_next_agent
from backend.events import broadcast_agent_thinking
from backend.flow_logger import log_flow

logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    investigation: InvestigationState
    messages: Annotated[List[Any], add_messages]
    current_agent: Optional[str]   # plain agent name string, e.g. "cicd_analyzer"
    should_continue: bool
    next_action: str


def create_initial_state(incident: Incident, max_iterations: int = 5) -> InvestigationState:
    return InvestigationState(
        incident=incident,
        incident_id=incident.incident_id,
        max_iterations=max_iterations,
        investigation_status=InvestigationStatus.PENDING,
    )


# ---------------------------------------------------------------------------
# Static pipeline nodes
# ---------------------------------------------------------------------------

def normalize_incident(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    investigation.investigation_status = InvestigationStatus.RUNNING
    logger.info(f"normalize_incident: {investigation.investigation_id}")
    return {"investigation": investigation, "next_action": "pre_filter"}


def rule_based_pre_filter(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    incident = investigation.incident

    evidence_gaps: List[str] = []
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

    if any(kw in description or kw in title for kw in ["database", "connection refused", "upstream", "downstream", "dependency", "cannot connect"]):
        evidence_gaps.append("dependency_health")
        if initial_hypothesis == HypothesisType.UNKNOWN:
            initial_hypothesis = HypothesisType.DEPENDENCY_ISSUE

    if any(kw in description or kw in title for kw in ["traffic", "spike", "surge", "load"]):
        evidence_gaps.append("traffic_pattern")
        if initial_hypothesis == HypothesisType.UNKNOWN:
            initial_hypothesis = HypothesisType.TRAFFIC_INCIDENT

    investigation.current_hypothesis = initial_hypothesis
    investigation.evidence_gaps = evidence_gaps
    logger.info(
        f"rule_based_pre_filter: {investigation.investigation_id}, "
        f"hypothesis={initial_hypothesis}, gaps={evidence_gaps}"
    )
    log_flow(
        investigation.investigation_id, "pre_filter",
        incident_id=incident.incident_id, title=incident.title,
        hypothesis=initial_hypothesis, evidence_gaps=evidence_gaps,
    )
    return {"investigation": investigation, "next_action": "load_evidence"}


def load_evidence(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    logger.info(
        f"load_evidence: {investigation.investigation_id}, "
        f"existing={len(investigation.evidence)}"
    )

    has_github_evidence = any(
        ev.source in ("github_actions", "github_actions_job_logs")
        for ev in investigation.evidence
    )

    if not has_github_evidence:
        investigation.evidence.extend(get_cicd_evidence(investigation.incident))

    investigation.evidence.extend(get_kubernetes_evidence(investigation.incident))
    investigation.evidence.extend(get_observability_evidence(investigation.incident))

    logger.info(
        f"load_evidence: {investigation.investigation_id}, "
        f"total={len(investigation.evidence)}"
    )
    log_flow(
        investigation.investigation_id, "load_evidence",
        total_evidence=len(investigation.evidence),
        sources=sorted({str(ev.source) for ev in investigation.evidence}),
    )
    return {"investigation": investigation, "next_action": "route"}


# ---------------------------------------------------------------------------
# Router node — asks the LLM router to choose the next specialist by name
# ---------------------------------------------------------------------------

async def adaptive_router(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    logger.info(
        f"adaptive_router: {investigation.investigation_id}, "
        f"iteration={investigation.iteration_count}"
    )

    if investigation.iteration_count >= investigation.max_iterations:
        investigation.investigation_status = InvestigationStatus.MAX_ITERATIONS_REACHED
        log_flow(
            investigation.investigation_id, "route_stopped",
            reason="max_iterations", iteration=investigation.iteration_count,
        )
        return {
            "investigation": investigation,
            "next_action": "generate_rca",
            "should_continue": False,
        }

    # Discover available agents from loaded md files
    from backend.runtime.agent_loader import get_specialist_agent_names
    all_specialist_names = get_specialist_agent_names()

    agents_invoked: List[str] = investigation.agents_invoked
    available_agents = [a for a in all_specialist_names if a not in agents_invoked]
    if not available_agents:
        available_agents = list(all_specialist_names)  # allow re-invocation when all exhausted

    runner = await get_agent_runner()
    critic_feedback = runner.format_critic_feedback(investigation.critic_reviews)

    evidence_summary = _format_evidence_summary(investigation.evidence)
    findings_summary = _format_findings_summary(investigation.agent_findings)

    router_started = time.perf_counter()
    selected_agent, reasoning = await runner.run_router_agent(
        incident=investigation.incident,
        current_hypothesis=investigation.current_hypothesis,
        evidence_gaps=investigation.evidence_gaps,
        agents_invoked=agents_invoked,
        available_agents=available_agents,
        evidence_summary=evidence_summary,
        findings_summary=findings_summary,
        critic_feedback=critic_feedback,
    )

    llm_choice = selected_agent
    router_fallback = selected_agent not in available_agents
    router_ms = round((time.perf_counter() - router_started) * 1000)

    # Validate — fall back to deterministic router if LLM returned something unknown
    if selected_agent not in available_agents:
        selected_agent, fallback_reason = select_next_agent(investigation, available_agents)
        reasoning = f"LLM router returned unavailable agent; deterministic fallback: {fallback_reason}"

    decision = RoutingDecision(
        investigation_id=investigation.investigation_id,
        iteration=investigation.iteration_count,
        current_hypothesis=investigation.current_hypothesis,
        evidence_gaps=investigation.evidence_gaps,
        agents_invoked=agents_invoked,
        available_agents=available_agents,
        selected_agent=selected_agent,
        reasoning=reasoning,
    )
    investigation.routing_decisions.append(decision)
    investigation.iteration_count += 1
    log_flow(
        investigation.investigation_id, "route",
        iteration=investigation.iteration_count,
        selected_agent=selected_agent, llm_choice=llm_choice,
        used_deterministic_fallback=router_fallback,
        available_agents=available_agents, agents_invoked=agents_invoked,
        hypothesis=investigation.current_hypothesis,
        evidence_gaps=investigation.evidence_gaps,
        reasoning=reasoning, duration_ms=router_ms,
    )
    logger.info(
        f"adaptive_router: {investigation.investigation_id}, "
        f"selected={selected_agent}"
    )

    return {
        "investigation": investigation,
        "current_agent": selected_agent,
        "next_action": "invoke_agent",
        "should_continue": True,
    }


# ---------------------------------------------------------------------------
# Generic agent invocation node — handles ANY specialist agent by name
# ---------------------------------------------------------------------------

async def invoke_agent(state: GraphState) -> GraphState:
    """Single generic node that dispatches to whichever agent the router chose."""
    investigation = state["investigation"]
    agent_name: str = state["current_agent"]

    logger.info(
        f"invoke_agent: {investigation.investigation_id}, agent={agent_name}"
    )

    runner = await get_agent_runner()

    await broadcast_agent_thinking(investigation.investigation_id, agent_name, "started")
    agent_started = time.perf_counter()
    try:
        finding = await runner.run_analysis_agent(
            agent_name=agent_name,
            incident=investigation.incident,
            evidence=investigation.evidence,
            previous_findings=investigation.agent_findings,
            critic_feedback=runner.format_critic_feedback(investigation.critic_reviews),
        )
    except Exception as exc:
        log_flow(
            investigation.investigation_id, "agent_failed",
            agent=agent_name, error=repr(exc),
            duration_ms=round((time.perf_counter() - agent_started) * 1000),
        )
        await broadcast_agent_thinking(investigation.investigation_id, agent_name, "failed")
        raise

    finding.investigation_id = investigation.investigation_id
    finding.iteration = investigation.iteration_count

    investigation.agent_findings.append(finding)
    investigation.agents_invoked.append(agent_name)
    logger.info(
        f"invoke_agent: {investigation.investigation_id}, "
        f"agent={agent_name}, finding={finding.finding[:100]}"
    )

    # Update confidence scores
    matching_evidence = [
        item for item in investigation.evidence
        if item.evidence_id in finding.evidence
    ]
    investigation.confidence_scores[agent_name] = (
        finding.confidence if matching_evidence else 0.0
    )
    log_flow(
        investigation.investigation_id, "agent_finding",
        agent=agent_name, iteration=investigation.iteration_count,
        hypothesis=finding.hypothesis, confidence=finding.confidence,
        grounded_evidence=len(matching_evidence),
        cited_evidence=len(finding.evidence),
        finding=finding.finding[:300],
        duration_ms=round((time.perf_counter() - agent_started) * 1000),
    )

    # Resolve evidence gaps covered by this finding
    gap_evidence_types: Dict[str, set] = {
        "deployment_details": {EvidenceType.DEPLOYMENT, EvidenceType.CODE_CHANGE, EvidenceType.JOB_FAILURE},
        "configuration_changes": {EvidenceType.CONFIG_CHANGE},
        "pod_memory_status": {EvidenceType.POD_EXIT_CODE, EvidenceType.RESOURCE_USAGE, EvidenceType.RESOURCE_LIMIT, EvidenceType.POD_EVENT},
        "pod_restart_pattern": {EvidenceType.POD_RESTART_COUNT, EvidenceType.POD_EVENT},
        "resource_pressure": {EvidenceType.RESOURCE_USAGE, EvidenceType.RESOURCE_LIMIT},
        "observability_metrics": {EvidenceType.LATENCY, EvidenceType.ERROR_RATE},
        "error_patterns": {EvidenceType.LOG, EvidenceType.STACK_TRACE, EvidenceType.ERROR_STATUS},
        "trace_analysis": {EvidenceType.TRACE, EvidenceType.SPAN_DURATION},
        "dependency_health": {EvidenceType.TRACE, EvidenceType.SPAN_DURATION, EvidenceType.DEPENDENCY_CHANGE, EvidenceType.ERROR_STATUS},
        "traffic_pattern": {EvidenceType.LATENCY, EvidenceType.ERROR_RATE},
    }
    resolved_gaps = {
        gap for gap in investigation.evidence_gaps
        if gap in gap_evidence_types
        and any(item.evidence_type in gap_evidence_types[gap] for item in matching_evidence)
    }
    investigation.evidence_gaps = [
        gap for gap in investigation.evidence_gaps if gap not in resolved_gaps
    ]

    await broadcast_agent_thinking(investigation.investigation_id, agent_name, "completed")
    return {"investigation": investigation, "next_action": "evaluate"}


# ---------------------------------------------------------------------------
# Evaluate + RCA + Persist nodes
# ---------------------------------------------------------------------------

def evaluate_evidence(state: GraphState) -> GraphState:
    return _evaluate_evidence(state["investigation"])


def _evaluate_evidence(investigation: InvestigationState) -> GraphState:
    from backend.orchestrator.confidence import calculate_overall_confidence
    from backend.config import settings

    evidence_ids = {item.evidence_id for item in investigation.evidence}
    grounded_confidences = {
        finding.agent_type: finding.confidence
        for finding in investigation.agent_findings
        if finding.evidence and any(ref in evidence_ids for ref in finding.evidence)
    }
    overall_confidence = calculate_overall_confidence(grounded_confidences)
    investigation.overall_confidence = overall_confidence

    entry = ConfidenceEntry(
        investigation_id=investigation.investigation_id,
        iteration=investigation.iteration_count,
        agent_confidences=grounded_confidences.copy(),
        overall_confidence=overall_confidence,
        threshold=settings.confidence_threshold,
        is_sufficient=overall_confidence >= settings.confidence_threshold,
    )
    investigation.confidence_history.append(entry)
    log_flow(
        investigation.investigation_id, "evaluate",
        iteration=investigation.iteration_count,
        agent_confidences=grounded_confidences,
        overall_confidence=overall_confidence,
        threshold=settings.confidence_threshold,
        is_sufficient=entry.is_sufficient,
    )

    if overall_confidence >= settings.confidence_threshold:
        investigation.investigation_status = InvestigationStatus.COMPLETED
        return {"investigation": investigation, "next_action": "generate_rca", "should_continue": False}
    elif investigation.iteration_count >= investigation.max_iterations:
        investigation.investigation_status = InvestigationStatus.MAX_ITERATIONS_REACHED
        return {"investigation": investigation, "next_action": "generate_rca", "should_continue": False}
    else:
        return {"investigation": investigation, "next_action": "route", "should_continue": True}


async def critique(state: GraphState) -> GraphState:
    """
    Verifier step between evaluation and the RCA.  A `challenged` verdict sends the
    investigation back to the router (bounded by critic_max_rounds, max_iterations
    and the specialists still unused); otherwise it proceeds to the RCA with the
    confidence capped by the critic's own assessment.
    """
    from backend.config import settings
    from backend.runtime.agent_loader import get_specialist_agent_names

    investigation = state["investigation"]
    if not settings.enable_critic or not investigation.agent_findings:
        return {"investigation": investigation, "next_action": "generate_rca", "should_continue": False}

    runner = await get_agent_runner()
    unused = [a for a in get_specialist_agent_names() if a not in investigation.agents_invoked]
    round_no = len(investigation.critic_reviews) + 1

    started = time.perf_counter()
    await broadcast_agent_thinking(investigation.investigation_id, "critic", "started")
    review = await runner.run_critic_agent(
        incident=investigation.incident,
        agent_findings=investigation.agent_findings,
        evidence=investigation.evidence,
        agents_invoked=investigation.agents_invoked,
        available_agents=unused,
        previous_reviews=investigation.critic_reviews,
        round_no=round_no,
        investigation_id=investigation.investigation_id,
    )
    investigation.critic_reviews.append(review)
    if review.verdict == "challenged":
        investigation.overall_confidence = min(investigation.overall_confidence, review.confidence)

    can_loop = (
        review.verdict == "challenged"
        and round_no < settings.critic_max_rounds
        and investigation.iteration_count < investigation.max_iterations
        and bool(unused)
    )
    log_flow(
        investigation.investigation_id, "critic",
        round=round_no, verdict=review.verdict, hypothesis=review.assessed_hypothesis,
        confidence=review.confidence, concerns=review.concerns,
        missing_checks=review.missing_checks, suggested_agent=review.suggested_agent,
        looping_back=can_loop, duration_ms=round((time.perf_counter() - started) * 1000),
    )
    await broadcast_agent_thinking(investigation.investigation_id, "critic", "completed")

    if can_loop:
        investigation.investigation_status = InvestigationStatus.RUNNING
        for check in review.missing_checks:
            gap = f"critic: {check}"
            if gap not in investigation.evidence_gaps:
                investigation.evidence_gaps.append(gap)
        return {"investigation": investigation, "next_action": "route", "should_continue": True}

    return {"investigation": investigation, "next_action": "generate_rca", "should_continue": False}


async def generate_rca(state: GraphState) -> GraphState:
    return await _generate_rca(state["investigation"])


async def _generate_rca(investigation: InvestigationState) -> GraphState:
    runner = await get_agent_runner()

    rca = await runner.run_rca_agent(
        incident=investigation.incident,
        agent_findings=investigation.agent_findings,
        evidence=investigation.evidence,
        routing_decisions=investigation.routing_decisions,
        confidence_history=investigation.confidence_history,
        critic_feedback=runner.format_critic_feedback(investigation.critic_reviews),
    )
    rca.investigation_id = investigation.investigation_id
    investigation.root_cause = rca

    remediation = await runner.run_remediation_agent(
        root_cause=rca.root_cause if rca else "Unknown",
        root_cause_type=rca.root_cause_type if rca else HypothesisType.UNKNOWN,
        confidence=investigation.overall_confidence,
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
    log_flow(
        investigation.investigation_id, "rca",
        status=investigation.investigation_status,
        root_cause_type=rca.root_cause_type if rca else None,
        overall_confidence=investigation.overall_confidence,
        agents_invoked=investigation.agents_invoked,
        iterations=investigation.iteration_count,
        critic_rounds=len(investigation.critic_reviews),
    )
    return {"investigation": investigation, "next_action": "persist", "should_continue": False}


async def persist_investigation(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    return {"investigation": investigation, "next_action": "end"}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_investigation_graph() -> StateGraph:
    workflow = StateGraph(GraphState)

    # Static pipeline nodes
    workflow.add_node("normalize", normalize_incident)
    workflow.add_node("pre_filter", rule_based_pre_filter)
    workflow.add_node("load_evidence", load_evidence)
    workflow.add_node("route", adaptive_router)

    # Single generic specialist node — handles every agent type
    workflow.add_node("invoke_agent", invoke_agent)

    workflow.add_node("evaluate", evaluate_evidence)
    workflow.add_node("critique", critique)
    workflow.add_node("generate_rca", generate_rca)
    workflow.add_node("persist", persist_investigation)

    # Linear pipeline
    workflow.add_edge(START, "normalize")
    workflow.add_edge("normalize", "pre_filter")
    workflow.add_edge("pre_filter", "load_evidence")
    workflow.add_edge("load_evidence", "route")

    # Route decision: invoke agent or go straight to RCA
    def route_decision(state: GraphState) -> str:
        action = state.get("next_action")
        if action in ("finalize", "generate_rca"):
            return "generate_rca"
        return "invoke_agent"

    workflow.add_conditional_edges(
        "route",
        route_decision,
        {
            "invoke_agent": "invoke_agent",
            "generate_rca": "generate_rca",
        },
    )

    workflow.add_edge("invoke_agent", "evaluate")

    # After evaluation: loop back to router or proceed to RCA
    workflow.add_conditional_edges(
        "evaluate",
        lambda state: state["next_action"],
        {
            "route": "route",
            "generate_rca": "critique",
        },
    )

    # Critic: challenge sends the investigation back to the router, otherwise write the RCA
    workflow.add_conditional_edges(
        "critique",
        lambda state: state["next_action"],
        {
            "route": "route",
            "generate_rca": "generate_rca",
        },
    )

    workflow.add_edge("generate_rca", "persist")
    workflow.add_edge("persist", END)

    return workflow.compile()


# ---------------------------------------------------------------------------
# Formatting helpers (used by adaptive_router and tests)
# ---------------------------------------------------------------------------

def _format_evidence_summary(evidence: list) -> str:
    if not evidence:
        return "No evidence collected yet."
    lines = []
    for ev in evidence[-10:]:
        lines.append(
            f"  - evidence_id={ev.evidence_id} [{ev.agent_type}] "
            f"{ev.evidence_type}: {ev.description[:200]}"
        )
    return "\n".join(lines)


def _format_findings_summary(findings: list) -> str:
    if not findings:
        return "No agent findings yet."
    lines = []
    for f in findings[-5:]:
        lines.append(
            f"  - [{f.agent_type}] {f.hypothesis}: "
            f"{f.finding[:100]} (confidence: {f.confidence:.2f})"
        )
    return "\n".join(lines)
