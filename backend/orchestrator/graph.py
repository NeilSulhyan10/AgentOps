"""
Investigation Graph

The investigation is a LangGraph state machine.  Each node is one function in
this file, in the order an investigation meets them:

    normalize -> pre_filter -> load_evidence -> spawn_agent -> route -> invoke_agent -> evaluate
                                                  ^            ^            |             |
                                                  |            |            |   not sure  |
                                                  |            |            +-------------+
                                                  |            |                          | confident
                                                  |            |  challenged              v
                                                  |            +---------------------- critique
                                                  |                                       | confirmed
                                                  +-- (spawn_agent creates a specialist   v
                                                       only when no existing one covers  generate_rca -> persist
                                                       a problem, then hands over to route)

A single generic `invoke_agent` node handles ALL specialist agents.  The router
writes the chosen agent name (the stem of a file in agents/markdown/) into
GraphState["current_agent"], so adding a specialist means adding a .md file.

Every node is wrapped by `_logged`, which writes a `node_failed` flow event
naming the node when it raises.  That is how a flow report knows where an
investigation broke.

To run the graph use `run_investigation` in backend/orchestrator/run.py.
"""

import inspect
import re
import logging
import time
from datetime import datetime
from typing import Annotated, Any, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

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
from backend.config import settings
from backend.events import broadcast_agent_thinking
from backend.flow.log import log_flow
from backend.orchestrator.router import select_next_agent
from backend.runtime import get_agent_runner
from backend.tools.data_access import get_cicd_evidence_from_fixture, get_kubernetes_evidence, get_observability_evidence

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


def _without_negated(text: str) -> str:
    """Lower-case text with clauses like 'no OOM', 'not ready', 'without errors' removed."""
    return re.sub(r"\b(?:no|not|without|never|zero|nor)\b[^.;,\n]{0,60}", " ", text.lower())


def rule_based_pre_filter(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    incident = investigation.incident

    evidence_gaps: List[str] = []
    initial_hypothesis = HypothesisType.UNKNOWN

    # "No recent deployments" must not look like a deployment: drop negated clauses first.
    description = _without_negated(incident.description)
    title = _without_negated(incident.title)

    if any(kw in description or kw in title for kw in ["deployment", "deploy", "rollout", "canary", "release"]):
        evidence_gaps.append("deployment_details")
        initial_hypothesis = HypothesisType.DEPLOYMENT_INDUCED_FAILURE

    if any(kw in description or kw in title for kw in ["oom", "memory", "killed", "exit code 137", "137"]):
        evidence_gaps.append("pod_memory_status")
        initial_hypothesis = HypothesisType.KUBERNETES_OOM

    if any(kw in description or kw in title for kw in ["crashloop", "restart", "crash"]):
        evidence_gaps.append("pod_restart_pattern")

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

    # Problems no standard specialist owns (cache, queue, DNS, disk...) become "<focus>_health" gaps;
    # the spawn_agent node creates a specialist for each.
    from backend.runtime.spawner import find_focuses
    for focus in find_focuses(f"{title} {description}")[:2]:
        evidence_gaps.append(f"{focus.key}_health")

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

    # Incidents created by the GitHub monitor arrive with their CI/CD evidence
    # attached.  Everything else is read from the fixture files in data/.
    has_github_evidence = any(
        ev.source in ("github_actions", "github_actions_job_logs")
        for ev in investigation.evidence
    )
    if settings.fault_injection == "missing_evidence":
        investigation.evidence.clear()   # demo fault: pretend nothing could be loaded
    else:
        if not has_github_evidence:
            investigation.evidence.extend(get_cicd_evidence_from_fixture(investigation.incident))
        investigation.evidence.extend(get_kubernetes_evidence(investigation.incident))
        investigation.evidence.extend(get_observability_evidence(investigation.incident))

    for item in investigation.evidence:
        item.investigation_id = investigation.investigation_id

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
# Spawn node - creates a specialist when nothing available covers a problem
# ---------------------------------------------------------------------------

def specialist_names(investigation_id: str) -> List[str]:
    """Specialists the router may pick: the .md files plus anything spawned for this investigation."""
    from backend.runtime.agent_loader import get_specialist_agent_names
    from backend.runtime.spawner import spawned_for
    return get_specialist_agent_names() + [n for n in spawned_for(investigation_id) if n not in get_specialist_agent_names()]


def spawn_requests(investigation: InvestigationState) -> list:
    """What could need a new specialist: gaps the pre-filter could not assign to anyone, and what the critic says is missing."""
    from backend.runtime.spawner import FOCUS_CATALOG, requests_from_text

    requests = [
        (FOCUS_CATALOG[gap[:-7]], f"The incident mentions {FOCUS_CATALOG[gap[:-7]].title.lower()} and no specialist covers it: \"{investigation.incident.title}\"")
        for gap in investigation.evidence_gaps if gap.endswith("_health") and gap[:-7] in FOCUS_CATALOG
    ]
    if investigation.critic_reviews and investigation.critic_reviews[-1].verdict == "challenged":
        last = investigation.critic_reviews[-1]
        requests += requests_from_text(list(last.missing_checks) + list(last.concerns))
    return requests


def spawn_agent(state: GraphState) -> GraphState:
    """Create specialists for problems no available specialist covers (see backend/runtime/spawner.py)."""
    from backend.runtime.spawner import spawn

    investigation = state["investigation"]
    made = spawn(investigation.investigation_id, spawn_requests(investigation), specialist_names(investigation.investigation_id))
    for spec in made:
        gap = f"{spec.name.replace('_analyzer', '')}_health"
        if gap not in investigation.evidence_gaps:
            investigation.evidence_gaps.insert(0, gap)
        log_flow(
            investigation.investigation_id, "agent_spawned",
            agent=spec.name, layer=spec.layer, hypothesis=spec.hypothesis,
            description=spec.description, keywords=spec.keywords, reason=spec.reason,
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
    all_specialist_names = specialist_names(investigation.investigation_id)

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
        investigation_id=investigation.investigation_id,
    )

    llm_choice = selected_agent
    router_fallback = selected_agent not in available_agents
    router_ms = round((time.perf_counter() - router_started) * 1000)

    # No usable LLM choice (rule-based mode, unusable answer, or an unknown agent name):
    # the rule-based router decides.
    if selected_agent not in available_agents:
        selected_agent, reasoning = select_next_agent(investigation, available_agents)
        if llm_choice:
            reasoning = f"LLM chose unavailable agent '{llm_choice}'; rule-based router: {reasoning}"

    investigation.iteration_count += 1
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
            investigation_id=investigation.investigation_id,
        )
    except Exception:
        # The `_logged` wrapper records the failure in the flow log; here we only tell the UI.
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
    from backend.orchestrator.scoring import score_finding
    investigation.confidence_scores[agent_name] = score_finding(finding, investigation.evidence).score
    log_flow(
        investigation.investigation_id, "agent_finding",
        agent=agent_name, iteration=investigation.iteration_count,
        hypothesis=finding.hypothesis, confidence=finding.confidence,
        grounded_evidence=len(matching_evidence),
        cited_evidence=len(finding.evidence), evidence_ids=list(finding.evidence),
        reasoning=finding.reasoning[:400],
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
    from backend.orchestrator.scoring import score_investigation

    breakdown = score_investigation(investigation.agent_findings, investigation.evidence, investigation.evidence_gaps)
    grounded_confidences = {f.agent: f.score for f in breakdown.findings if f.grounding > 0}
    overall_confidence = breakdown.overall
    investigation.overall_confidence = overall_confidence
    from backend.orchestrator.causal import found_nothing
    from backend.orchestrator.critic import grounded_findings
    all_clear = found_nothing(grounded_findings(investigation.agent_findings, investigation.evidence))

    entry = ConfidenceEntry(
        investigation_id=investigation.investigation_id,
        iteration=investigation.iteration_count,
        agent_confidences=grounded_confidences.copy(),
        overall_confidence=overall_confidence,
        threshold=settings.confidence_threshold,
        is_sufficient=overall_confidence >= settings.confidence_threshold or all_clear,
    )
    investigation.confidence_history.append(entry)
    log_flow(
        investigation.investigation_id, "evaluate",
        iteration=investigation.iteration_count,
        agent_confidences=grounded_confidences,
        overall_confidence=overall_confidence,
        threshold=settings.confidence_threshold,
        is_sufficient=entry.is_sufficient,
        all_clear=all_clear, breakdown=breakdown.to_dict(),
    )

    # Only generate_rca sets a finished status; "completed" before the RCA exists would be a lie.
    if entry.is_sufficient:
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
    investigation = state["investigation"]
    if not settings.enable_critic or not investigation.agent_findings:
        return {"investigation": investigation, "next_action": "generate_rca", "should_continue": False}

    runner = await get_agent_runner()
    unused = [a for a in specialist_names(investigation.investigation_id) if a not in investigation.agents_invoked]
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
        evidence_gaps=list(investigation.evidence_gaps),
    )
    investigation.critic_reviews.append(review)
    from backend.orchestrator.scoring import score_investigation
    breakdown = score_investigation(investigation.agent_findings, investigation.evidence, investigation.evidence_gaps, review)
    investigation.overall_confidence = breakdown.overall      # a challenge that is still open lowers it (x0.8)

    can_spawn = bool(spawn_requests(investigation)) if review.verdict == "challenged" else False
    can_loop = (
        review.verdict == "challenged"
        and round_no < settings.critic_max_rounds
        and investigation.iteration_count < investigation.max_iterations
        and (bool(unused) or can_spawn)
    )
    log_flow(
        investigation.investigation_id, "critic",
        round=round_no, verdict=review.verdict, hypothesis=review.assessed_hypothesis,
        confidence=review.confidence, concerns=review.concerns,
        missing_checks=review.missing_checks, suggested_agent=review.suggested_agent,
        looping_back=can_loop, breakdown=breakdown.to_dict(),
        duration_ms=round((time.perf_counter() - started) * 1000),
    )
    await broadcast_agent_thinking(investigation.investigation_id, "critic", "completed")

    if can_loop:
        investigation.investigation_status = InvestigationStatus.RUNNING
        for check in review.missing_checks:
            gap = f"critic: {check}"
            if gap not in investigation.evidence_gaps:
                investigation.evidence_gaps.append(gap)
        return {"investigation": investigation, "next_action": "spawn_agent", "should_continue": True}

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
        investigation_id=investigation.investigation_id,
    )
    rca.investigation_id = investigation.investigation_id
    investigation.root_cause = rca

    remediation = await runner.run_remediation_agent(
        root_cause=rca.root_cause if rca else "Unknown",
        root_cause_type=rca.root_cause_type if rca else HypothesisType.UNKNOWN,
        confidence=investigation.overall_confidence,
        investigation_id=investigation.investigation_id,
    )
    remediation.investigation_id = investigation.investigation_id
    remediation.rca_id = rca.rca_id if rca else ""
    investigation.remediation = remediation

    if investigation.investigation_status not in (
        InvestigationStatus.MAX_ITERATIONS_REACHED,
        InvestigationStatus.INSUFFICIENT_EVIDENCE,
    ):
        investigation.investigation_status = InvestigationStatus.COMPLETED

    investigation.completed_at = datetime.utcnow()
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

def _logged(node_name: str, node: Callable) -> Callable:
    """Wrap a node so that an exception is written to the flow log with the node's name."""

    async def run_node(state: GraphState):
        started = time.perf_counter()
        try:
            result = node(state)
            return await result if inspect.isawaitable(result) else result
        except Exception as exc:
            log_flow(
                state["investigation"].investigation_id, "node_failed",
                node=node_name,
                agent=state.get("current_agent") if node_name == "invoke_agent" else None,
                error=f"{type(exc).__name__}: {exc}",
                duration_ms=round((time.perf_counter() - started) * 1000),
            )
            raise

    return run_node


def build_investigation_graph() -> StateGraph:
    """
    Wire the nodes together.  backend/flow/diagram.py draws this same graph;
    tests/test_flow.py fails if the two drift apart.
    """
    workflow = StateGraph(GraphState)

    nodes = {
        "normalize": normalize_incident,
        "pre_filter": rule_based_pre_filter,
        "load_evidence": load_evidence,
        "spawn_agent": spawn_agent,
        "route": adaptive_router,
        "invoke_agent": invoke_agent,      # one generic node for every specialist
        "evaluate": evaluate_evidence,
        "critique": critique,
        "generate_rca": generate_rca,
        "persist": persist_investigation,
    }
    for name, node in nodes.items():
        workflow.add_node(name, _logged(name, node))

    # Linear pipeline
    workflow.add_edge(START, "normalize")
    workflow.add_edge("normalize", "pre_filter")
    workflow.add_edge("pre_filter", "load_evidence")
    workflow.add_edge("load_evidence", "spawn_agent")
    workflow.add_edge("spawn_agent", "route")

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
            "spawn_agent": "spawn_agent",
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
