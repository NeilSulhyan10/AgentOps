from typing import Dict, List, Optional
from backend.models import (
    InvestigationState,
    RootCauseAnalysis,
    RemediationRecommendation,
    AgentType,
    HypothesisType,
    AgentFinding,
    Evidence,
    EvidenceType,
    RoutingDecision
)


DEFAULT_CONFIDENCE_THRESHOLD = 0.75


def calculate_overall_confidence(agent_confidences: Dict[AgentType, float]) -> float:
    if not agent_confidences:
        return 0.0

    product = 1.0
    for confidence in agent_confidences.values():
        product *= (1.0 - confidence)

    overall = 1.0 - product
    return round(overall, 4)


def is_confidence_sufficient(overall_confidence: float, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> bool:
    return overall_confidence >= threshold


def get_confidence_level(overall_confidence: float) -> str:
    if overall_confidence >= 0.9:
        return "very_high"
    elif overall_confidence >= 0.75:
        return "high"
    elif overall_confidence >= 0.5:
        return "medium"
    elif overall_confidence >= 0.25:
        return "low"
    return "very_low"


def synthesize_rca(investigation: InvestigationState) -> RootCauseAnalysis:
    findings = investigation.agent_findings
    evidence = investigation.evidence

    if not findings:
        return RootCauseAnalysis(
            investigation_id=investigation.investigation_id,
            incident_id=investigation.incident_id,
            root_cause="Insufficient evidence to determine root cause",
            root_cause_type=HypothesisType.UNKNOWN,
            overall_confidence=investigation.overall_confidence,
            agents_consulted=investigation.agents_invoked
        )

    # Filter to only AgentFinding objects for processing
    valid_findings = [f for f in findings if isinstance(f, AgentFinding)]
    
    if not valid_findings:
        return RootCauseAnalysis(
            investigation_id=investigation.investigation_id,
            incident_id=investigation.incident_id,
            root_cause="Insufficient evidence to determine root cause",
            root_cause_type=HypothesisType.UNKNOWN,
            overall_confidence=investigation.overall_confidence,
            agents_consulted=investigation.agents_invoked
        )

    primary_finding = max(valid_findings, key=lambda f: f.confidence)
    contributing_factors = []
    evidence_refs = []

    for finding in findings:
        if isinstance(finding, AgentFinding):
            # agent_type is stored as string due to use_enum_values=True in Pydantic config
            agent_type_str = finding.agent_type if isinstance(finding.agent_type, str) else finding.agent_type.value
            contributing_factors.append(f"{agent_type_str}: {finding.finding}")
            evidence_refs.extend(finding.evidence)
        else:
            contributing_factors.append(str(finding))

    for ev in evidence:
        if isinstance(ev, Evidence):
            ev_type_str = ev.evidence_type if isinstance(ev.evidence_type, str) else ev.evidence_type.value
            evidence_refs.append(f"{ev_type_str}: {ev.description}")
        else:
            evidence_refs.append(str(ev))

    timeline = []
    for i, finding in enumerate(findings):
        if isinstance(finding, AgentFinding):
            agent_type_str = finding.agent_type if isinstance(finding.agent_type, str) else finding.agent_type.value
            hypothesis_str = finding.hypothesis if isinstance(finding.hypothesis, str) else finding.hypothesis.value
            timeline.append({
                "step": i + 1,
                "agent": agent_type_str,
                "hypothesis": hypothesis_str,
                "finding": finding.finding,
                "confidence": finding.confidence,
                "timestamp": finding.timestamp.isoformat()
            })
        else:
            timeline.append({
                "step": i + 1,
                "agent": "unknown",
                "hypothesis": "unknown",
                "finding": str(finding),
                "confidence": 0,
                "timestamp": ""
            })

    for i, decision in enumerate(investigation.routing_decisions):
        if isinstance(decision, RoutingDecision):
            selected_agent_str = decision.selected_agent if isinstance(decision.selected_agent, str) else decision.selected_agent.value
            timeline.append({
                "step": len(findings) + i + 1,
                "type": "routing_decision",
                "selected_agent": selected_agent_str,
                "reasoning": decision.reasoning,
                "timestamp": decision.timestamp.isoformat()
            })
        else:
            timeline.append({
                "step": len(findings) + i + 1,
                "type": "routing_decision",
                "selected_agent": "unknown",
                "reasoning": str(decision),
                "timestamp": ""
            })

    root_cause = _generate_root_cause_text(findings, investigation.incident)

    return RootCauseAnalysis(
        investigation_id=investigation.investigation_id,
        incident_id=investigation.incident_id,
        root_cause=root_cause,
        root_cause_type=primary_finding.hypothesis,
        contributing_factors=contributing_factors,
        evidence=list(set(evidence_refs)),
        agents_consulted=investigation.agents_invoked,
        overall_confidence=investigation.overall_confidence,
        investigation_timeline=timeline
    )


def _generate_root_cause_text(findings: List[AgentFinding], incident) -> str:
    if not findings:
        return "Unable to determine root cause - no agent findings available."

    # Filter to only AgentFinding objects for max calculation
    valid_findings = [f for f in findings if isinstance(f, AgentFinding)]
    if not valid_findings:
        return "Unable to determine root cause - no valid agent findings available."

    primary = max(valid_findings, key=lambda f: f.confidence)

    templates = {
        HypothesisType.DEPLOYMENT_INDUCED_FAILURE: (
            "Recent deployment caused the incident. "
            "{details}"
        ),
        HypothesisType.KUBERNETES_OOM: (
            "Kubernetes pod was OOMKilled due to memory exhaustion. "
            "{details}"
        ),
        HypothesisType.APPLICATION_ERROR: (
            "Application error detected in the service. "
            "{details}"
        ),
        HypothesisType.CONFIGURATION_ERROR: (
            "Configuration change caused the incident. "
            "{details}"
        ),
        HypothesisType.DEPENDENCY_ISSUE: (
            "External dependency failure caused the incident. "
            "{details}"
        ),
        HypothesisType.TRAFFIC_INCIDENT: (
            "Traffic spike or anomaly caused service degradation. "
            "{details}"
        ),
        HypothesisType.MULTI_LAYER_FAILURE: (
            "Multi-layer failure detected across multiple components. "
            "{details}"
        )
    }

    template = templates.get(primary.hypothesis, "{details}")
    details = primary.finding

    if len(findings) > 1:
        other_findings = [f for f in findings if isinstance(f, AgentFinding) and f != primary]
        details += f" Additional factors: {'; '.join(f.finding for f in other_findings)}"

    return template.format(details=details)


def generate_remediation(rca: RootCauseAnalysis) -> RemediationRecommendation:
    remediation_templates = {
        HypothesisType.DEPLOYMENT_INDUCED_FAILURE: {
            "recommendation": "Rollback the recent deployment and investigate the failing changes",
            "steps": [
                "Identify the deployment that introduced the issue",
                "Rollback to the previous stable version",
                "Analyze the changes in the failed deployment",
                "Fix the issue in a new branch",
                "Deploy with canary rollout and monitoring"
            ],
            "priority": "high",
            "estimated_effort": "medium",
            "risk_level": "low"
        },
        HypothesisType.KUBERNETES_OOM: {
            "recommendation": "Increase memory limits or optimize application memory usage",
            "steps": [
                "Analyze memory usage patterns",
                "Increase memory limit in deployment configuration",
                "Consider adding memory requests for QoS guarantees",
                "Deploy with canary rollout",
                "Monitor memory usage post-deployment"
            ],
            "priority": "high",
            "estimated_effort": "low",
            "risk_level": "low"
        },
        HypothesisType.APPLICATION_ERROR: {
            "recommendation": "Fix the application bug and deploy hotfix",
            "steps": [
                "Analyze stack trace and error logs",
                "Identify the root cause in application code",
                "Develop and test fix",
                "Deploy hotfix with minimal blast radius",
                "Verify fix resolves the issue"
            ],
            "priority": "high",
            "estimated_effort": "medium",
            "risk_level": "medium"
        },
        HypothesisType.CONFIGURATION_ERROR: {
            "recommendation": "Revert configuration change and validate configuration management process",
            "steps": [
                "Identify the configuration change that caused the issue",
                "Revert to previous known-good configuration",
                "Review configuration validation process",
                "Add configuration validation tests",
                "Re-apply configuration with proper validation"
            ],
            "priority": "high",
            "estimated_effort": "low",
            "risk_level": "low"
        },
        HypothesisType.DEPENDENCY_ISSUE: {
            "recommendation": "Mitigate dependency failure and improve resilience",
            "steps": [
                "Identify the failing dependency",
                "Implement circuit breaker or fallback",
                "Contact dependency owner if external",
                "Add dependency health monitoring",
                "Consider caching or alternative providers"
            ],
            "priority": "medium",
            "estimated_effort": "medium",
            "risk_level": "medium"
        },
        HypothesisType.TRAFFIC_INCIDENT: {
            "recommendation": "Scale resources and implement traffic management",
            "steps": [
                "Scale up affected services horizontally",
                "Implement rate limiting if needed",
                "Add auto-scaling rules for traffic spikes",
                "Review capacity planning",
                "Implement graceful degradation"
            ],
            "priority": "high",
            "estimated_effort": "medium",
            "risk_level": "low"
        },
        HypothesisType.MULTI_LAYER_FAILURE: {
            "recommendation": "Address each layer systematically starting with the most impactful",
            "steps": [
                "Prioritize fixes by impact and confidence",
                "Address infrastructure layer issues first",
                "Then application layer issues",
                "Then configuration/dependency issues",
                "Verify end-to-end resolution"
            ],
            "priority": "high",
            "estimated_effort": "high",
            "risk_level": "medium"
        }
    }

    template = remediation_templates.get(
        rca.root_cause_type,
        {
            "recommendation": "Investigate further and apply appropriate remediation",
            "steps": ["Analyze findings", "Develop remediation plan", "Execute and verify"],
            "priority": "medium",
            "estimated_effort": "medium",
            "risk_level": "medium"
        }
    )

    return RemediationRecommendation(
        investigation_id=rca.investigation_id,
        rca_id=rca.rca_id,
        **template
    )