"""
Agent Runner

Runs one agent step: build the prompt from the agent's Markdown definition, ask
the LLM, check the answer against a schema.  Every step has a rule-based twin:

    LLM gave a valid answer    -> use it
    rule-based mode (no LLM)   -> use the rules; this is normal, nothing is logged
    LLM answer was unusable    -> use the rules AND log `llm_parse_fallback`,
                                  so the flow report shows the step in amber

`_ask_llm` is the only place that talks to the LLM.
"""

import json
import time
import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from backend.flow.log import log_flow
from backend.llm.observe import record_call
from backend.llm import LLMProvider, LLMRequest, get_llm_provider
from backend.llm.schemas import AgentAnalysisResponse, RoutingDecisionResponse, RCAResponse, RemediationResponse, CriticResponse
from backend.models import HypothesisType, EvidenceType, Evidence, Incident, AgentFinding, RootCauseAnalysis, RemediationRecommendation, CriticReview

logger = logging.getLogger(__name__)

Answer = TypeVar("Answer", bound=BaseModel)

_HYPOTHESES = "deployment_induced_failure|kubernetes_oom|traffic_incident|configuration_error|dependency_issue|application_error|multi_layer_failure|unknown"


def extract_json(text: str) -> str:
    """Return the JSON object inside an LLM answer (models often wrap it in ```json fences or prose)."""
    start, end = text.find("{"), text.rfind("}")
    return text[start:end + 1] if 0 <= start < end else text


class AgentRunner:
    """Executes agents using loaded Markdown definitions and the configured LLM provider."""

    def __init__(self, agent_definitions: Dict[str, str]):
        self.agent_definitions = agent_definitions

    @property
    def llm(self) -> LLMProvider:
        return get_llm_provider()

    def _build_prompt(self, agent_name: str, input_data: Dict[str, Any], output_schema: str, investigation_id: str = "") -> str:
        from backend.runtime.spawner import spawned_prompt
        definition = self.agent_definitions.get(agent_name) or spawned_prompt(investigation_id, agent_name)
        if not definition:
            raise ValueError(f"Agent definition not found: {agent_name}")
        return f"""{definition}

## Current Input
{json.dumps(input_data, indent=2, default=str)}

## Required Output Format
{output_schema}

Respond with JSON only."""

    async def _ask_llm(
        self,
        task: str,
        prompt_name: str,
        input_data: Dict[str, Any],
        output_schema: str,
        system_prompt: str,
        answer_model: Type[Answer],
        investigation_id: str,
        max_tokens: int = 2048,
        agent: str = "",
    ) -> Optional[Answer]:
        """
        Ask the LLM and return its validated answer, or None when the caller
        must use its rule-based implementation (see the module docstring).
        """
        request = LLMRequest(
            prompt=self._build_prompt(prompt_name, input_data, output_schema, investigation_id),
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=max_tokens,
            metadata={"task": task, "agent": agent, "investigation_id": investigation_id},
        )
        started = time.perf_counter()
        response = await self.llm.generate(request)
        record_call(investigation_id, task, agent, request, response, round((time.perf_counter() - started) * 1000))
        if response.skipped:
            return None
        try:
            if response.error:
                raise ValueError(f"LLM call failed: {response.error}")
            return answer_model.model_validate_json(extract_json(response.content))
        except (ValidationError, ValueError) as exc:
            logger.warning("LLM answer for %s %s unusable, using rules: %s", task, agent, exc)
            log_flow(investigation_id, "llm_parse_fallback", task=task, agent=agent, error=_one_line(exc))
            return None

    # ------------------------------------------------------------------
    # One method per kind of agent.  Each asks the LLM, else uses rules.
    # ------------------------------------------------------------------

    async def run_analysis_agent(
        self,
        agent_name: str,
        incident: Incident,
        evidence: List[Evidence],
        previous_findings: Optional[List[AgentFinding]] = None,
        critic_feedback: str = "",
        investigation_id: str = "",
    ) -> AgentFinding:
        """Run the specialist whose Markdown file is `<agent_name>.md` and return its finding."""
        input_data = {
            "incident": {**_incident_brief(incident), "incident_id": incident.incident_id},
            "evidence": self._format_evidence(evidence),
            "previous_findings": self._format_findings(previous_findings or []),
        }
        if critic_feedback:
            input_data["critic_feedback"] = critic_feedback

        answer = await self._ask_llm(
            task="analysis", prompt_name=agent_name, agent=agent_name,
            input_data=input_data,
            output_schema=f"""{{
  "hypothesis": "{_HYPOTHESES}",
  "finding": "Human-readable finding description",
  "evidence": ["exact evidence_id values from the supplied evidence"],
  "confidence": 0.85,
  "reasoning": "Combined reasoning from all matched evidence"
}}""",
            system_prompt=(
                f"You are a {agent_name} specialist investigating a DevOps incident. "
                "Analyze the evidence and provide a structured finding. "
                "In the evidence array, include only exact evidence_id values shown in "
                "the supplied evidence; use an empty array if none support the finding. "
                "Respond with JSON only."
            ),
            answer_model=AgentAnalysisResponse,
            investigation_id=investigation_id,
        )
        if answer is None:
            return self._rule_based_finding(agent_name, incident, evidence, investigation_id)
        return AgentFinding(
            investigation_id=investigation_id,
            agent_type=agent_name,
            hypothesis=answer.hypothesis,
            finding=answer.finding,
            evidence=answer.evidence,
            confidence=answer.confidence,
            reasoning=answer.reasoning,
        )

    async def run_router_agent(
        self,
        incident: Incident,
        current_hypothesis: Optional[HypothesisType],
        evidence_gaps: List[str],
        agents_invoked: List[str],
        available_agents: List[str],
        evidence_summary: str,
        findings_summary: str,
        critic_feedback: str = "",
        investigation_id: str = "",
    ) -> tuple[str, str]:
        """
        Ask the router which specialist to run next.  Returns (agent_name, reasoning).
        agent_name is "" when the LLM gave no usable answer; the caller then uses
        the rule-based router (backend/orchestrator/router.py).
        """
        input_data = {
            "incident": _incident_brief(incident),
            "current_hypothesis": _text(current_hypothesis) or "unknown",
            "evidence_gaps": evidence_gaps,
            "agents_invoked": agents_invoked,
            "available_agents": available_agents,
            "evidence_collected": evidence_summary,
            "agent_findings": findings_summary,
        }
        if critic_feedback:
            input_data["critic_feedback"] = critic_feedback

        answer = await self._ask_llm(
            task="routing", prompt_name="router",
            input_data=input_data,
            output_schema=f"""{{
  "selected_agent": "{"|".join(available_agents)}",
  "reasoning": "Detailed explanation of why this agent was selected",
  "confidence": 0.85
}}""",
            system_prompt=(
                "You are an expert DevOps incident investigator. "
                "Select the most relevant specialist agent to investigate next based on "
                "the evidence gaps and current hypothesis. "
                f"You MUST select from this exact list: {available_agents}. "
                "Respond with JSON only."
            ),
            answer_model=RoutingDecisionResponse,
            investigation_id=investigation_id,
            max_tokens=1024,
        )
        if answer is None:
            return "", ""
        return answer.selected_agent.strip().lower(), answer.reasoning

    async def run_critic_agent(
        self,
        incident: Incident,
        agent_findings: List[AgentFinding],
        evidence: List[Evidence],
        agents_invoked: List[str],
        available_agents: List[str],
        previous_reviews: List[CriticReview],
        round_no: int,
        investigation_id: str = "",
        evidence_gaps: Optional[List[str]] = None,
    ) -> CriticReview:
        """Review the combined findings before the RCA is written."""
        answer = await self._ask_llm(
            task="critic", prompt_name="critic",
            input_data={
                "incident": _incident_brief(incident),
                "agent_findings": self._format_findings(agent_findings),
                "evidence": self._format_evidence(evidence),
                "agents_invoked": agents_invoked,
                "available_agents": available_agents,
                "previous_reviews": self.format_critic_feedback(previous_reviews) or "None",
            },
            output_schema=f"""{{
  "verdict": "confirmed|challenged",
  "hypothesis": "{_HYPOTHESES}",
  "concerns": ["..."],
  "missing_checks": ["..."],
  "suggested_agent": "name from available_agents or null",
  "confidence": 0.8,
  "reasoning": "..."
}}""",
            system_prompt=(
                "You are a critical reviewer of a DevOps incident investigation. "
                "Findings from different specialists are parts of one causal chain, not competing answers. "
                "Challenge the conclusion only when something concrete is missing. "
                f"suggested_agent MUST be one of {available_agents} or null. Respond with JSON only."
            ),
            answer_model=CriticResponse,
            investigation_id=investigation_id,
            max_tokens=1024,
        )
        if answer is None:
            from backend.orchestrator.critic import deterministic_review
            return deterministic_review(agent_findings, evidence, available_agents, round_no, investigation_id, evidence_gaps)

        suggested = answer.suggested_agent.strip().lower() if answer.suggested_agent else None
        return CriticReview(
            investigation_id=investigation_id, round=round_no, verdict=answer.verdict,
            assessed_hypothesis=answer.hypothesis, concerns=answer.concerns,
            missing_checks=answer.missing_checks,
            suggested_agent=suggested if suggested in available_agents else None,
            confidence=answer.confidence, reasoning=answer.reasoning,
        )

    @staticmethod
    def format_critic_feedback(reviews: List[CriticReview]) -> str:
        """Render the latest review as text for the router, specialists and RCA writer."""
        if not reviews:
            return ""
        r = reviews[-1]
        parts = [f"Critic round {r.round}: {r.verdict} (confidence {r.confidence:.2f}) on '{r.assessed_hypothesis}'."]
        if r.concerns:
            parts.append("Concerns: " + "; ".join(r.concerns))
        if r.missing_checks:
            parts.append("Missing checks: " + "; ".join(r.missing_checks))
        if r.suggested_agent:
            parts.append(f"Suggested next agent: {r.suggested_agent}")
        return " ".join(parts)

    async def run_rca_agent(
        self,
        incident: Incident,
        agent_findings: List[AgentFinding],
        evidence: List[Evidence],
        routing_decisions: List,
        confidence_history: List,
        critic_feedback: str = "",
        investigation_id: str = "",
    ) -> RootCauseAnalysis:
        """Write the root cause analysis from everything the specialists found."""
        input_data = {
            "incident": _incident_brief(incident),
            "agent_findings": self._format_findings(agent_findings),
            "evidence": self._format_evidence(evidence),
            "routing_decisions": self._format_routing(routing_decisions),
            "confidence_history": self._format_confidence(confidence_history),
        }
        if critic_feedback:
            input_data["critic_review"] = critic_feedback

        answer = await self._ask_llm(
            task="rca", prompt_name="rca_synthesizer",
            input_data=input_data,
            output_schema=f"""{{
  "root_cause": "What happened: ...\\nWhy it happened: ...\\nAnalogy: ... (include this line only when a short, accurate analogy helps)",
  "root_cause_type": "{_HYPOTHESES}",
  "contributing_factors": ["factor1", "factor2"],
  "confidence": 0.85
}}""",
            system_prompt=(
                "You are an expert incident investigator writing for a general audience. "
                "Explain the root cause in plain, everyday language with short sentences; "
                "define necessary technical terms and clearly separate confirmed evidence from uncertainty. "
                "In root_cause, use labeled What happened and Why it happened lines. Add one short, "
                "accurate everyday Analogy line only when it genuinely clarifies the evidence; otherwise omit it. "
                "Keep contributing factors easy to understand, preserve the required enum value, and respond with JSON only."
            ),
            answer_model=RCAResponse,
            investigation_id=investigation_id,
        )
        if answer is None:
            from backend.orchestrator.confidence import synthesize_rca
            # Minimal stand-in exposing the fields synthesize_rca reads
            from backend.orchestrator.critic import grounded_findings
            # Findings that cite no real evidence must not decide the root cause.
            trusted = grounded_findings(agent_findings, evidence)
            return synthesize_rca(SimpleNamespace(
                agent_findings=trusted,
                evidence=evidence,
                routing_decisions=routing_decisions,
                incident=incident,
                incident_id=incident.incident_id,
                investigation_id=investigation_id,
                agents_invoked=list(dict.fromkeys(f.agent_type for f in agent_findings)),
                overall_confidence=max((f.confidence for f in trusted), default=0.1),
            ))
        return RootCauseAnalysis(
            investigation_id=investigation_id,
            incident_id=incident.incident_id,
            root_cause=answer.root_cause,
            root_cause_type=answer.root_cause_type,
            contributing_factors=answer.contributing_factors,
            overall_confidence=answer.confidence,
        )

    async def run_remediation_agent(
        self,
        root_cause: str,
        root_cause_type: HypothesisType | str,
        confidence: float,
        investigation_id: str = "",
    ) -> RemediationRecommendation:
        """Turn the root cause into a remediation plan."""
        answer = await self._ask_llm(
            task="remediation", prompt_name="remediation_planner",
            input_data={
                "root_cause": root_cause,
                "root_cause_type": _text(root_cause_type),
                "confidence": confidence,
            },
            output_schema="""{
  "recommendation": "High-level remediation summary",
  "steps": ["step1", "step2", "step3"],
  "priority": "high|medium|low",
  "estimated_effort": "low|medium|high",
  "risk_level": "low|medium|high"
}""",
            system_prompt=(
                "You are an expert DevOps incident investigator. Generate a remediation plan "
                "based on the root cause analysis. Respond with JSON only."
            ),
            answer_model=RemediationResponse,
            investigation_id=investigation_id,
        )
        if answer is None:
            from backend.orchestrator.confidence import generate_remediation
            # Minimal stand-in exposing the fields generate_remediation reads (the caller sets the real ids)
            return generate_remediation(SimpleNamespace(investigation_id=investigation_id, rca_id="", root_cause_type=root_cause_type))
        return RemediationRecommendation(
            investigation_id=investigation_id,
            rca_id="",  # set by the caller once the RCA has an id
            recommendation=answer.recommendation,
            steps=answer.steps,
            priority=answer.priority,
            estimated_effort=answer.estimated_effort,
            risk_level=answer.risk_level,
        )

    # ------------------------------------------------------------------
    # Rule-based specialists
    # ------------------------------------------------------------------

    def _rule_based_finding(self, agent_name: str, incident: Incident, evidence: List[Evidence], investigation_id: str = "") -> AgentFinding:
        """
        The rule-based twin of a specialist.  Built-in specialists have a Python
        class; the others use a keyword profile; an agent with neither reports
        that it found nothing.
        """
        from backend.agents.cicd.agent import CICDAgent
        from backend.agents.kubernetes.agent import KubernetesAgent
        from backend.agents.observability.agent import ObservabilityAgent

        agent_class_map = {
            "cicd_analyzer": CICDAgent,
            "kubernetes_analyzer": KubernetesAgent,
            "observability_analyzer": ObservabilityAgent,
        }

        cls = agent_class_map.get(agent_name)
        if cls:
            finding = cls().investigate(incident, evidence)
            # Ensure agent_type is the string name used by the caller
            finding.agent_type = agent_name
            return finding

        from backend.runtime.agent_loader import get_agent_spec
        from backend.runtime.spawner import spawned_for
        spec = get_agent_spec(agent_name) or spawned_for(investigation_id).get(agent_name)
        if spec and spec.has_rules:
            finding = self._profile_finding(agent_name, spec, incident, evidence)
            if finding:
                return finding

        # Nothing matched (or the agent has no rules at all): report "found nothing".
        return AgentFinding(
            investigation_id="",
            agent_type=agent_name,
            hypothesis="unknown",
            finding=f"{agent_name} found nothing in the evidence that points to its kind of problem.",
            evidence=[],
            confidence=0.0,
            reasoning="Rule-based check: no evidence matched this specialist's patterns.",
            iteration=0,
        )
    
    def _profile_finding(self, agent_name: str, spec, incident: Incident, evidence: List[Evidence]) -> Optional[AgentFinding]:
        """Keyword/evidence-type finding for specialists without a Python class, capped so it never outweighs a real analysis."""
        context = f"{incident.title} {incident.description}".lower()
        if spec.incident_keywords and not any(k in context for k in spec.incident_keywords):
            return None
        matched = [
            ev for ev in evidence
            if str(getattr(ev.evidence_type, "value", ev.evidence_type)) in spec.evidence_types
            and any(k in f"{ev.description} {json.dumps(ev.raw_data, default=str)}".lower() for k in spec.keywords)
        ]
        if not matched:
            return None
        top = matched[:3]
        return AgentFinding(
            investigation_id="",
            agent_type=agent_name,
            hypothesis=spec.hypothesis,
            finding=f"{spec.description.split(':')[0]}: " + "; ".join(ev.description[:120] for ev in top),
            evidence=[ev.evidence_id for ev in top],
            confidence=min(spec.max_confidence, 0.5 + 0.05 * len(matched)),
            reasoning="Rule-based check: matched evidence by type and keyword.",
            iteration=0,
        )

    # ------------------------------------------------------------------
    # Prompt formatting helpers
    # ------------------------------------------------------------------
    def _format_evidence(self, evidence: List[Evidence], limit: int = 40) -> str:
        if not evidence:
            return "No evidence collected yet."
        lines = []
        for ev in evidence[-limit:]:
            lines.append(f"  - evidence_id={ev.evidence_id} [{ev.agent_type}] {ev.evidence_type}: {ev.description[:300]}")
        return "\n".join(lines)
    
    def _format_findings(self, findings: List[AgentFinding]) -> str:
        if not findings:
            return "No agent findings yet."
        lines = []
        for f in findings[-5:]:
            lines.append(f"  - [{f.agent_type}] {f.hypothesis}: {f.finding[:100]} (confidence: {f.confidence:.2f})")
        return "\n".join(lines)
    
    def _format_routing(self, decisions: List) -> str:
        if not decisions:
            return "No routing decisions yet."
        lines = []
        for d in decisions:
            lines.append(f"  - Iteration {d.iteration}: routed to {d.selected_agent} ({d.reasoning})")
        return "\n".join(lines)
    
    def _format_confidence(self, history: List) -> str:
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


def _one_line(exc: Exception) -> str:
    """First useful line of an error: pydantic's multi-line messages end with a docs link nobody needs."""
    lines = [l.strip() for l in str(exc).splitlines() if l.strip() and "errors.pydantic.dev" not in l]
    return " ".join(lines[:2])[:200]


def _incident_brief(incident: Incident) -> Dict[str, str]:
    return {
        "title": incident.title,
        "description": incident.description,
        "service_name": incident.service_name,
        "namespace": incident.namespace,
    }


def _text(value: Any) -> str:
    """Enum or plain string -> plain string."""
    return getattr(value, "value", value) or ""


# Global runner instance
_runner: Optional[AgentRunner] = None


async def get_agent_runner() -> AgentRunner:
    """Get or create the global agent runner."""
    global _runner
    if _runner is None:
        from backend.runtime.agent_loader import load_all_agent_definitions
        definitions = load_all_agent_definitions()
        _runner = AgentRunner(definitions)
    return _runner


async def reload_agent_runner() -> AgentRunner:
    """Reload agent definitions and recreate runner."""
    global _runner
    from backend.runtime.agent_loader import reload_agent_definitions
    definitions = reload_agent_definitions()
    _runner = AgentRunner(definitions)
    return _runner
