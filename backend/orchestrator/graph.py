from typing import Dict, List, Any, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
import operator

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
from backend.llm import get_llm_provider, LLMRequest
from backend.llm.schemas import RoutingDecisionResponse, AgentAnalysisResponse, RCAResponse, RemediationResponse
from backend.tools.data_access import get_cicd_evidence, get_kubernetes_evidence, get_observability_evidence


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

    return {"investigation": investigation, "next_action": "load_evidence"}


def load_evidence(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    
    cicd_evidence = get_cicd_evidence(investigation.incident)
    k8s_evidence = get_kubernetes_evidence(investigation.incident)
    obs_evidence = get_observability_evidence(investigation.incident)
    
    investigation.evidence.extend(cicd_evidence)
    investigation.evidence.extend(k8s_evidence)
    investigation.evidence.extend(obs_evidence)
    investigation.updated_at = investigation.updated_at
    
    return {"investigation": investigation, "next_action": "route"}


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


async def adaptive_router(state: GraphState) -> GraphState:
    investigation = state["investigation"]

    if investigation.iteration_count >= investigation.max_iterations:
        investigation.investigation_status = InvestigationStatus.MAX_ITERATIONS_REACHED
        return {"investigation": investigation, "next_action": "finalize", "should_continue": False}

    agents_invoked = investigation.agents_invoked
    evidence_gaps = investigation.evidence_gaps
    current_hypothesis = investigation.current_hypothesis

    available_agents = [a for a in AgentType if a not in agents_invoked]
    if not available_agents:
        available_agents = list(AgentType)

    llm = get_llm_provider()
    prompt = f"""ROUTE: Select the next specialist agent to investigate.

Incident: {investigation.incident.title} - {investigation.incident.description}
Service: {investigation.incident.service_name}
Namespace: {investigation.incident.namespace}

Current hypothesis: {current_hypothesis.value if current_hypothesis else 'UNKNOWN'}
Evidence gaps: {', '.join(evidence_gaps) if evidence_gaps else 'None'}
Agents already invoked: {[a.value for a in agents_invoked] if agents_invoked else 'None'}
Available agents: {[a.value for a in available_agents]}

Evidence collected so far:
{_format_evidence_summary(investigation.evidence)}

Agent findings so far:
{_format_findings_summary(investigation.agent_findings)}

Select the next agent to investigate based on the evidence gaps and current hypothesis.
Respond with JSON only in this exact format:
{{
  "selected_agent": "cicd|kubernetes|observability",
  "reasoning": "your reasoning here",
  "confidence": 0.85
}}
"""

    routing_response = await get_llm_provider().generate(LLMRequest(
        prompt=prompt,
        system_prompt="You are an expert DevOps incident investigator. Select the most relevant specialist agent to investigate next based on the evidence gaps and current hypothesis. Respond with JSON only.",
        temperature=0.1,
        max_tokens=1024
    ))

    try:
        routing_data = RoutingDecisionResponse.model_validate_json(routing_response.content)
        selected_agent = routing_data.selected_agent
        reasoning = routing_data.reasoning
    except Exception:
        selected_agent = available_agents[0] if available_agents else AgentType.CICD
        reasoning = "Fallback to deterministic routing"

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

    return {
        "investigation": investigation,
        "current_agent": selected_agent,
        "next_action": "invoke_agent",
        "should_continue": True
    }


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


def invoke_cicd_agent(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    return _invoke_agent(investigation, AgentType.CICD)


def invoke_kubernetes_agent(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    return _invoke_agent(investigation, AgentType.KUBERNETES)


def invoke_observability_agent(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    return _invoke_agent(investigation, AgentType.OBSERVABILITY)


def _invoke_agent(investigation: InvestigationState, agent_type: AgentType) -> GraphState:
    from backend.agents.cicd.agent import CICDAgent
    from backend.agents.kubernetes.agent import KubernetesAgent
    from backend.agents.observability.agent import ObservabilityAgent
    from backend.llm.schemas import AgentAnalysisResponse
    import asyncio

    agents = {
        AgentType.CICD: CICDAgent(),
        AgentType.KUBERNETES: KubernetesAgent(),
        AgentType.OBSERVABILITY: ObservabilityAgent()
    }

    agent = agents[agent_type]

    llm = get_llm_provider()
    prompt = f"""ANALYZE: Agent {agent_type.value} investigating incident.

Incident: {investigation.incident.title} - {investigation.incident.description}
Service: {investigation.incident.service_name}
Namespace: {investigation.incident.namespace}

Current hypothesis: {investigation.current_hypothesis.value if investigation.current_hypothesis else 'UNKNOWN'}

Evidence available:
{_format_evidence_summary(investigation.evidence)}

Previous findings:
{_format_findings_summary(investigation.agent_findings)}

Analyze the evidence and provide your finding, hypothesis, evidence references, confidence, and reasoning.
Respond with JSON only in this exact format:
{{
  "finding": "your finding here",
  "hypothesis": "deployment_induced_failure|kubernetes_oom|traffic_incident|configuration_error|dependency_issue|unknown",
  "evidence": ["evidence1", "evidence2"],
  "confidence": 0.85,
  "reasoning": "your reasoning here"
}}
"""

    analysis_response = asyncio.run(llm.generate(LLMRequest(
        prompt=prompt,
        system_prompt=f"You are a {agent_type.value} specialist investigating a DevOps incident. Analyze the evidence and provide a structured finding. Respond with JSON only.",
        temperature=0.1,
        max_tokens=2048
    )))

    try:
        analysis_data = AgentAnalysisResponse.model_validate_json(analysis_response.content)
        finding = AgentFinding(
            investigation_id=investigation.investigation_id,
            agent_type=agent_type,
            hypothesis=analysis_data.hypothesis,
            finding=analysis_data.finding,
            evidence=analysis_data.evidence,
            confidence=analysis_data.confidence,
            reasoning=analysis_data.reasoning,
            timestamp=datetime.utcnow(),
            iteration=investigation.iteration_count
        )
    except Exception:
        # Fallback to deterministic agent
        agent = {
            AgentType.CICD: CICDAgent(),
            AgentType.KUBERNETES: KubernetesAgent(),
            AgentType.OBSERVABILITY: ObservabilityAgent()
        }[agent_type]
        finding = agent.investigate(investigation.incident, investigation.evidence)

    investigation.agent_findings.append(finding)
    investigation.agents_invoked.append(agent_type)
    investigation.confidence_scores[agent_type] = finding.confidence
    investigation.updated_at = investigation.updated_at

    if finding.evidence:
        investigation.evidence_gaps = [g for g in investigation.evidence_gaps if g not in finding.evidence]

    return {"investigation": investigation, "next_action": "evaluate"}


def evaluate_evidence(state: GraphState) -> GraphState:
    investigation = state["investigation"]
    return _evaluate_evidence(investigation)


def _evaluate_evidence(investigation: InvestigationState) -> GraphState:
    from backend.orchestrator.confidence import calculate_overall_confidence

    overall_confidence = calculate_overall_confidence(investigation.confidence_scores)
    investigation.overall_confidence = overall_confidence

    entry = ConfidenceEntry(
        investigation_id=investigation.investigation_id,
        iteration=investigation.iteration_count,
        agent_confidences=investigation.confidence_scores.copy(),
        overall_confidence=overall_confidence,
        threshold=0.75,
        is_sufficient=overall_confidence >= 0.75
    )
    investigation.confidence_history.append(entry)
    investigation.updated_at = investigation.updated_at

    if overall_confidence >= 0.75:
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
    llm = get_llm_provider()

    prompt = f"""RCA: Synthesize root cause analysis from investigation findings.

Incident: {investigation.incident.title} - {investigation.incident.description}
Service: {investigation.incident.service_name}
Namespace: {investigation.incident.namespace}

Agent findings:
{_format_findings_summary(investigation.agent_findings)}

Evidence collected:
{_format_evidence_summary(investigation.evidence)}

Routing decisions:
{_format_routing_summary(investigation.routing_decisions)}

Confidence history:
{_format_confidence_history(investigation.confidence_history)}

Synthesize a root cause analysis with root cause, root cause type, contributing factors, confidence, and investigation timeline.
Respond with JSON only in this exact format:
{{
  "root_cause": "your root cause description here",
  "root_cause_type": "deployment_induced_failure|kubernetes_oom|traffic_incident|configuration_error|dependency_issue|unknown",
  "contributing_factors": ["factor1", "factor2"],
  "confidence": 0.85
}}
"""

    rca_response = await get_llm_provider().generate(LLMRequest(
        prompt=prompt,
        system_prompt="You are an expert DevOps incident investigator. Synthesize a comprehensive root cause analysis from the investigation findings. Respond with JSON only.",
        temperature=0.1,
        max_tokens=2048
    ))

    try:
        rca_data = RCAResponse.model_validate_json(rca_response.content)
        rca = RootCauseAnalysis(
            investigation_id=investigation.investigation_id,
            incident_id=investigation.incident_id,
            root_cause=rca_data.root_cause,
            root_cause_type=rca_data.root_cause_type,
            contributing_factors=rca_data.contributing_factors,
            overall_confidence=rca_data.confidence
        )
    except Exception:
        # Fallback to deterministic RCA
        from backend.orchestrator.confidence import synthesize_rca
        rca = synthesize_rca(investigation)

    investigation.root_cause = rca

    # Generate remediation
    remediation_prompt = f"""REMEDIATION: Generate remediation plan for root cause.

Root cause: {investigation.root_cause.root_cause if investigation.root_cause else 'Unknown'}
Root cause type: {investigation.root_cause.root_cause_type if investigation.root_cause else 'unknown'}
Confidence: {investigation.overall_confidence:.2f}

Generate a remediation recommendation with steps, priority, effort, and risk level.
Respond with JSON only in this exact format:
{{
  "recommendation": "your recommendation here",
  "steps": ["step1", "step2"],
  "priority": "high|medium|low",
  "estimated_effort": "low|medium|high",
  "risk_level": "low|medium|high"
}}
"""

    try:
        remediation_data = RemediationResponse.model_validate_json(remediation_response.content)
        remediation = RemediationRecommendation(
            investigation_id=investigation.investigation_id,
            rca_id=investigation.root_cause.rca_id if investigation.root_cause else "",
            recommendation=remediation_data.recommendation,
            steps=remediation_data.steps,
            priority=remediation_data.priority,
            estimated_effort=remediation_data.estimated_effort,
            risk_level=remediation_data.risk_level
        )
    except Exception:
        from backend.orchestrator.confidence import generate_remediation
        remediation = generate_remediation(investigation.root_cause)

    investigation.remediation = remediation

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