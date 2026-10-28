"""
Critic / verifier support.

The critic reviews the specialists' combined findings before the RCA is written.
It does not decide which specialist is "right": findings from different layers
usually describe different links of one causal chain.  It checks that the
conclusion is grounded in real evidence, corroborated by more than one layer,
and free of unexplained contradictions, and asks for another specialist when
it is not.

`deterministic_review` is the rule-based fallback used when the LLM critic
returns unparseable output.
"""

from typing import List, Optional

from backend.models import (
    AgentFinding,
    CriticReview,
    Evidence,
    HypothesisType,
)

# Hypotheses that can legitimately sit alongside a different root-cause type in
# one causal chain (a change triggers a runtime failure, which surfaces as errors).
_CHAIN_HYPOTHESES = {
    HypothesisType.DEPLOYMENT_INDUCED_FAILURE,
    HypothesisType.MULTI_LAYER_FAILURE,
    HypothesisType.APPLICATION_ERROR,
}

# Which specialist best corroborates a given lead hypothesis, in preference order.
_CORROBORATORS: dict[HypothesisType, List[str]] = {
    HypothesisType.DEPLOYMENT_INDUCED_FAILURE: ["kubernetes_analyzer", "config_analyzer", "observability_analyzer"],
    HypothesisType.KUBERNETES_OOM: ["cicd_analyzer", "observability_analyzer", "traffic_analyzer"],
    HypothesisType.TRAFFIC_INCIDENT: ["observability_analyzer", "kubernetes_analyzer", "traffic_analyzer"],
    HypothesisType.CONFIGURATION_ERROR: ["config_analyzer", "cicd_analyzer", "kubernetes_analyzer"],
    HypothesisType.DEPENDENCY_ISSUE: ["dependency_analyzer", "observability_analyzer", "cicd_analyzer"],
    HypothesisType.APPLICATION_ERROR: ["observability_analyzer", "cicd_analyzer", "dependency_analyzer"],
}


def _value(x) -> str:
    return x if isinstance(x, str) else x.value


def grounded_findings(findings: List[AgentFinding], evidence: List[Evidence]) -> List[AgentFinding]:
    ids = {e.evidence_id for e in evidence}
    return [f for f in findings if f.evidence and any(ref in ids for ref in f.evidence)]


def pick_suggested_agent(lead: Optional[HypothesisType], unused: List[str]) -> Optional[str]:
    if not unused:
        return None
    for name in _CORROBORATORS.get(lead, []):
        if name in unused:
            return name
    return unused[0]


def deterministic_review(
    findings: List[AgentFinding],
    evidence: List[Evidence],
    unused_agents: List[str],
    round_no: int,
    investigation_id: str = "",
) -> CriticReview:
    grounded = grounded_findings(findings, evidence)

    if not grounded:
        return CriticReview(
            investigation_id=investigation_id, round=round_no, verdict="challenged",
            concerns=["No finding cites evidence that exists in this investigation."],
            missing_checks=["Gather grounded evidence from another specialist."],
            suggested_agent=pick_suggested_agent(None, unused_agents),
            confidence=0.2,
            reasoning="Every finding is ungrounded, so the conclusion cannot be verified.",
        )

    lead = max(grounded, key=lambda f: f.confidence)
    lead_h = HypothesisType(_value(lead.hypothesis))
    layers = {f.agent_type for f in grounded}

    concerns: List[str] = []
    missing: List[str] = []

    if len(layers) < 2:
        concerns.append(
            f"The '{lead_h.value}' conclusion rests on a single layer ({lead.agent_type}); nothing independent corroborates it."
        )
        missing.append("Independent corroboration from a different layer (CI/CD, Kubernetes, observability, config, dependencies or traffic).")

    for other in grounded:
        oh = HypothesisType(_value(other.hypothesis))
        if (
            other.confidence >= 0.6
            and oh != lead_h
            and oh != HypothesisType.UNKNOWN
            and not ({oh, lead_h} & _CHAIN_HYPOTHESES)
        ):
            concerns.append(
                f"{other.agent_type} reports '{oh.value}' while {lead.agent_type} reports '{lead_h.value}'; the two are not explained as one causal chain."
            )
            missing.append(f"Reconcile '{oh.value}' with '{lead_h.value}'.")
            break

    if concerns and unused_agents:
        suggested = pick_suggested_agent(lead_h, unused_agents)
        return CriticReview(
            investigation_id=investigation_id, round=round_no, verdict="challenged",
            assessed_hypothesis=lead_h, concerns=concerns, missing_checks=missing,
            suggested_agent=suggested,
            confidence=round(min(lead.confidence, 0.6), 2),
            reasoning="The conclusion is not yet corroborated or contains unreconciled findings; another specialist can resolve this.",
        )

    return CriticReview(
        investigation_id=investigation_id, round=round_no, verdict="confirmed",
        assessed_hypothesis=lead_h,
        concerns=concerns,  # any remaining concerns cannot be resolved with the specialists left
        confidence=round(lead.confidence if not concerns else min(lead.confidence, 0.7), 2),
        reasoning=(
            f"{len(layers)} layer(s) support '{lead_h.value}' with grounded evidence."
            if not concerns else
            "Remaining concerns cannot be investigated further; conclusion is reported with that caveat."
        ),
    )
