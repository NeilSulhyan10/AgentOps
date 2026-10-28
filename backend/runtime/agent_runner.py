"""
Agent Runner

Generic agent execution runtime that loads agent definitions from Markdown
and executes them using the LLM provider with structured output parsing.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Type

from backend.llm import get_llm_provider, LLMRequest
from backend.llm.schemas import AgentAnalysisResponse, RoutingDecisionResponse, RCAResponse, RemediationResponse, CriticResponse
from backend.flow_logger import log_flow
from backend.models import HypothesisType, EvidenceType, Evidence, Incident, AgentFinding, RootCauseAnalysis, RemediationRecommendation, CriticReview

logger = logging.getLogger(__name__)


# Fallback heuristics for dynamically discovered specialists (used only when the LLM output is unusable).
_DYNAMIC_AGENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "config_analyzer": {
        "hypothesis": HypothesisType.CONFIGURATION_ERROR,
        "summary": "Configuration change correlates with the failure:",
        "evidence_types": {EvidenceType.CONFIG_CHANGE, EvidenceType.POD_EVENT, EvidenceType.LOG},
        "keywords": ["probe", "env", "secret", "configmap", "config", "port", "unhealthy", "missing"],
        "incident_keywords": [],
    },
    "dependency_analyzer": {
        "hypothesis": HypothesisType.DEPENDENCY_ISSUE,
        "summary": "A dependency or downstream service is failing:",
        "evidence_types": {EvidenceType.LOG, EvidenceType.TRACE, EvidenceType.STACK_TRACE, EvidenceType.DEPENDENCY_CHANGE},
        "keywords": ["connection refused", "database", "upstream", "timeout", "importerror", "incompatible", "cannot import", "downstream"],
        "incident_keywords": [],
    },
    "traffic_analyzer": {
        "hypothesis": HypothesisType.TRAFFIC_INCIDENT,
        "summary": "Load on the service changed sharply:",
        "evidence_types": {EvidenceType.LATENCY, EvidenceType.ERROR_RATE, EvidenceType.LOG},
        "keywords": ["traffic", "requests", "p99", "rate", "saturat", "throttl"],
        "incident_keywords": ["traffic", "spike", "load", "surge", "latency"],
    },
}


class AgentRunner:
    """Executes agents using loaded Markdown definitions and LLM provider."""
    
    def __init__(self, agent_definitions: Dict[str, str]):
        self.agent_definitions = agent_definitions
        self.llm = get_llm_provider()
    
    def _build_prompt(self, agent_name: str, input_data: Dict[str, Any], output_schema: str) -> str:
        """Build the complete prompt for an agent."""
        definition = self.agent_definitions.get(agent_name)
        if not definition:
            raise ValueError(f"Agent definition not found: {agent_name}")
        
        # Extract the workflow and output format from definition
        prompt = f"""{definition}

## Current Input
{json.dumps(input_data, indent=2, default=str)}

## Required Output Format
{output_schema}

Respond with JSON only."""
        
        return prompt
    
    async def run_analysis_agent(
        self,
        agent_name: str,
        incident: Incident,
        evidence: List[Evidence],
        previous_findings: List[AgentFinding] = None,
        critic_feedback: str = "",
    ) -> AgentFinding:
        """
        Run a specialist analysis agent identified by its md file stem
        (e.g. 'cicd_analyzer', 'kubernetes_analyzer', or any dynamic agent).
        The agent type stored in the finding matches the agent_name string.
        """
        # Format evidence summary
        evidence_summary = self._format_evidence(evidence)
        findings_summary = self._format_findings(previous_findings or [])

        input_data = {
            "incident": {
                "incident_id": incident.incident_id,
                "title": incident.title,
                "description": incident.description,
                "service_name": incident.service_name,
                "namespace": incident.namespace,
            },
            "evidence": evidence_summary,
            "previous_findings": findings_summary,
        }
        if critic_feedback:
            input_data["critic_feedback"] = critic_feedback

        output_schema = """{
  "hypothesis": "deployment_induced_failure|kubernetes_oom|traffic_incident|configuration_error|dependency_issue|application_error|multi_layer_failure|unknown",
  "finding": "Human-readable finding description",
  "evidence": ["exact evidence_id values from the supplied evidence"],
  "confidence": 0.85,
  "reasoning": "Combined reasoning from all matched evidence"
}"""

        prompt = self._build_prompt(agent_name, input_data, output_schema)

        system_prompt = (
            f"You are a {agent_name} specialist investigating a DevOps incident. "
            "Analyze the evidence and provide a structured finding. "
            "In the evidence array, include only exact evidence_id values shown in "
            "the supplied evidence; use an empty array if none support the finding. "
            "Respond with JSON only."
        )

        response = await self.llm.generate(LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=2048,
            metadata={"task": "analysis", "agent": agent_name, "incident_id": incident.incident_id},
        ))

        try:
            analysis_data = AgentAnalysisResponse.model_validate_json(response.content)
            finding = AgentFinding(
                investigation_id="",  # Set by caller
                agent_type=agent_name,  # plain string — works for built-in and dynamic agents
                hypothesis=analysis_data.hypothesis,
                finding=analysis_data.finding,
                evidence=analysis_data.evidence,
                confidence=analysis_data.confidence,
                reasoning=analysis_data.reasoning,
                iteration=0,  # Set by caller
            )
            logger.info(f"Agent {agent_name} completed: {finding.finding[:100]}")
            return finding
        except Exception as e:
            logger.warning(f"LLM parsing failed for {agent_name}, using deterministic fallback: {e}")
            log_flow("", "llm_parse_fallback", incident_id=incident.incident_id, task="analysis", agent=agent_name, error=repr(e))
            return await self._run_deterministic_fallback(agent_name, incident, evidence)
    
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
    ) -> tuple[str, str]:
        """Run the router agent to select next specialist. Returns (agent_name, reasoning)."""

        input_data = {
            "incident": {
                "title": incident.title,
                "description": incident.description,
                "service_name": incident.service_name,
                "namespace": incident.namespace,
            },
            "current_hypothesis": current_hypothesis.value if current_hypothesis else "unknown",
            "evidence_gaps": evidence_gaps,
            "agents_invoked": agents_invoked,
            "available_agents": available_agents,
            "evidence_collected": evidence_summary,
            "agent_findings": findings_summary,
        }
        if critic_feedback:
            input_data["critic_feedback"] = critic_feedback

        # Build dynamic output schema listing the actual available agents
        agents_str = "|".join(available_agents) if available_agents else "cicd_analyzer|kubernetes_analyzer|observability_analyzer"
        output_schema = f"""{{\n  "selected_agent": "{agents_str}",\n  "reasoning": "Detailed explanation of why this agent was selected",\n  "confidence": 0.85\n}}"""

        prompt = self._build_prompt("router", input_data, output_schema)

        system_prompt = (
            "You are an expert DevOps incident investigator. "
            "Select the most relevant specialist agent to investigate next based on "
            "the evidence gaps and current hypothesis. "
            f"You MUST select from this exact list: {available_agents}. "
            "Respond with JSON only."
        )

        response = await self.llm.generate(LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=1024,
            metadata={"task": "routing", "incident_id": incident.incident_id},
        ))

        try:
            routing_data = RoutingDecisionResponse.model_validate_json(response.content)
            selected = routing_data.selected_agent
            # Normalise: strip whitespace, lower-case
            selected = selected.strip().lower()
            return selected, routing_data.reasoning
        except Exception as e:
            logger.warning(f"Router LLM parsing failed, using fallback: {e}")
            log_flow("", "llm_parse_fallback", incident_id=incident.incident_id, task="routing", error=repr(e))
            return "", "Fallback to deterministic routing"
    
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
    ) -> CriticReview:
        """Run the critic over the combined findings. Returns a CriticReview."""
        input_data = {
            "incident": {
                "title": incident.title,
                "description": incident.description,
                "service_name": incident.service_name,
                "namespace": incident.namespace,
            },
            "agent_findings": self._format_findings(agent_findings),
            "evidence": self._format_evidence(evidence),
            "agents_invoked": agents_invoked,
            "available_agents": available_agents,
            "previous_reviews": self.format_critic_feedback(previous_reviews) or "None",
        }

        output_schema = """{
  "verdict": "confirmed|challenged",
  "hypothesis": "deployment_induced_failure|kubernetes_oom|traffic_incident|configuration_error|dependency_issue|application_error|multi_layer_failure|unknown",
  "concerns": ["..."],
  "missing_checks": ["..."],
  "suggested_agent": "name from available_agents or null",
  "confidence": 0.8,
  "reasoning": "..."
}"""
        prompt = self._build_prompt("critic", input_data, output_schema)
        system_prompt = (
            "You are a critical reviewer of a DevOps incident investigation. "
            "Findings from different specialists are parts of one causal chain, not competing answers. "
            "Challenge the conclusion only when something concrete is missing. "
            f"suggested_agent MUST be one of {available_agents} or null. Respond with JSON only."
        )

        response = await self.llm.generate(LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=1024,
            metadata={"task": "critic", "incident_id": incident.incident_id},
        ))

        try:
            data = CriticResponse.model_validate_json(response.content)
            suggested = data.suggested_agent.strip().lower() if data.suggested_agent else None
            if suggested not in available_agents:
                suggested = None
            return CriticReview(
                investigation_id=investigation_id, round=round_no, verdict=data.verdict,
                assessed_hypothesis=data.hypothesis, concerns=data.concerns,
                missing_checks=data.missing_checks, suggested_agent=suggested,
                confidence=data.confidence, reasoning=data.reasoning,
            )
        except Exception as e:
            logger.warning(f"Critic LLM parsing failed, using deterministic review: {e}")
            log_flow("", "llm_parse_fallback", incident_id=incident.incident_id, task="critic", error=repr(e))
            from backend.orchestrator.critic import deterministic_review
            return deterministic_review(
                agent_findings, evidence, available_agents, round_no, investigation_id
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
    ) -> RootCauseAnalysis:
        """Run the RCA synthesis agent."""
        
        input_data = {
            "incident": {
                "title": incident.title,
                "description": incident.description,
                "service_name": incident.service_name,
                "namespace": incident.namespace,
            },
            "agent_findings": self._format_findings(agent_findings),
            "evidence": self._format_evidence(evidence),
            "routing_decisions": self._format_routing(routing_decisions),
            "confidence_history": self._format_confidence(confidence_history),
        }
        if critic_feedback:
            input_data["critic_review"] = critic_feedback
        
        output_schema = """{
  "root_cause": "What happened: ...\\nWhy it happened: ...\\nAnalogy: ... (include this line only when a short, accurate analogy helps)",
  "root_cause_type": "deployment_induced_failure|kubernetes_oom|traffic_incident|configuration_error|dependency_issue|application_error|multi_layer_failure|unknown",
  "contributing_factors": ["factor1", "factor2"],
  "confidence": 0.85
}"""
        
        prompt = self._build_prompt("rca_synthesizer", input_data, output_schema)
        
        system_prompt = (
            "You are an expert incident investigator writing for a general audience. "
            "Explain the root cause in plain, everyday language with short sentences; "
            "define necessary technical terms and clearly separate confirmed evidence from uncertainty. "
            "In root_cause, use labeled What happened and Why it happened lines. Add one short, "
            "accurate everyday Analogy line only when it genuinely clarifies the evidence; otherwise omit it. "
            "Keep contributing factors easy to understand, preserve the required enum value, and respond with JSON only."
        )
        
        response = await self.llm.generate(LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=2048,
            metadata={"task": "rca", "incident_id": incident.incident_id},
        ))
        
        try:
            rca_data = RCAResponse.model_validate_json(response.content)
            return RootCauseAnalysis(
                investigation_id="",  # Set by caller
                incident_id=incident.incident_id,
                root_cause=rca_data.root_cause,
                root_cause_type=rca_data.root_cause_type,
                contributing_factors=rca_data.contributing_factors,
                overall_confidence=rca_data.confidence
            )
        except Exception as e:
            logger.warning(f"RCA LLM parsing failed, using fallback: {e}")
            log_flow("", "llm_parse_fallback", incident_id=incident.incident_id, task="rca", error=repr(e))
            from backend.orchestrator.confidence import synthesize_rca
            from types import SimpleNamespace
            # Minimal stand-in exposing the fields synthesize_rca reads
            state = SimpleNamespace(
                agent_findings=agent_findings,
                evidence=evidence,
                routing_decisions=routing_decisions,
                incident=incident,
                incident_id=incident.incident_id,
                investigation_id="",
                agents_invoked=list(dict.fromkeys(f.agent_type for f in agent_findings)),
                overall_confidence=max((f.confidence for f in agent_findings), default=0.1),
            )
            return synthesize_rca(state)
    
    async def run_remediation_agent(
        self,
        root_cause: str,
        root_cause_type: HypothesisType | str,
        confidence: float
    ) -> RemediationRecommendation:
        """Run the remediation planning agent."""
        
        # Handle both enum and string cases
        if isinstance(root_cause_type, HypothesisType):
            root_cause_type_str = root_cause_type.value
        else:
            root_cause_type_str = str(root_cause_type)
        
        input_data = {
            "root_cause": root_cause,
            "root_cause_type": root_cause_type_str,
            "confidence": confidence,
        }
        
        output_schema = """{
  "recommendation": "High-level remediation summary",
  "steps": ["step1", "step2", "step3"],
  "priority": "high|medium|low",
  "estimated_effort": "low|medium|high",
  "risk_level": "low|medium|high"
}"""
        
        prompt = self._build_prompt("remediation_planner", input_data, output_schema)
        
        system_prompt = "You are an expert DevOps incident investigator. Generate a remediation plan based on the root cause analysis. Respond with JSON only."
        
        response = await self.llm.generate(LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=2048,
            metadata={"task": "remediation", "root_cause_type": root_cause_type_str},
        ))
        
        try:
            remediation_data = RemediationResponse.model_validate_json(response.content)
            return RemediationRecommendation(
                investigation_id="",  # Set by caller
                rca_id="",  # Set by caller
                recommendation=remediation_data.recommendation,
                steps=remediation_data.steps,
                priority=remediation_data.priority,
                estimated_effort=remediation_data.estimated_effort,
                risk_level=remediation_data.risk_level
            )
        except Exception as e:
            logger.warning(f"Remediation LLM parsing failed, using fallback: {e}")
            from backend.orchestrator.confidence import generate_remediation
            from types import SimpleNamespace
            # Minimal stand-in exposing the fields generate_remediation reads (the caller sets the real ids)
            rca = SimpleNamespace(investigation_id="", rca_id="", root_cause_type=root_cause_type)
            return generate_remediation(rca)
    
    async def _run_deterministic_fallback(
        self,
        agent_name: str,
        incident: Incident,
        evidence: List[Evidence]
    ) -> AgentFinding:
        """
        Run the deterministic Python agent as fallback when LLM parsing fails.
        For built-in agents the matching class is used; for unknown dynamic
        agents a minimal UNKNOWN finding is returned.
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

        profile = _DYNAMIC_AGENT_PROFILES.get(agent_name)
        if profile:
            finding = self._profile_finding(agent_name, profile, incident, evidence)
            if finding:
                return finding

        # Unknown dynamic agent — return a safe UNKNOWN finding
        logger.warning(
            f"No deterministic fallback for dynamic agent '{agent_name}'; "
            "returning UNKNOWN finding."
        )
        return AgentFinding(
            investigation_id="",
            agent_type=agent_name,
            hypothesis="unknown",
            finding=f"Agent '{agent_name}' failed and has no deterministic fallback.",
            evidence=[],
            confidence=0.0,
            reasoning="LLM failed and no deterministic fallback is registered for this agent.",
            iteration=0,
        )
    
    def _profile_finding(
        self,
        agent_name: str,
        profile: Dict[str, Any],
        incident: Incident,
        evidence: List[Evidence],
    ) -> Optional[AgentFinding]:
        """Keyword/evidence-type finding for dynamic specialists, capped so it never outweighs a real analysis."""
        context = f"{incident.title} {incident.description}".lower()
        if profile["incident_keywords"] and not any(k in context for k in profile["incident_keywords"]):
            return None
        matched = [
            ev for ev in evidence
            if ev.evidence_type in profile["evidence_types"]
            and any(k in f"{ev.description} {json.dumps(ev.raw_data, default=str)}".lower() for k in profile["keywords"])
        ]
        if not matched:
            return None
        top = matched[:3]
        return AgentFinding(
            investigation_id="",
            agent_type=agent_name,
            hypothesis=profile["hypothesis"],
            finding=profile["summary"] + " " + "; ".join(ev.description[:120] for ev in top),
            evidence=[ev.evidence_id for ev in top],
            confidence=min(0.65, 0.5 + 0.05 * len(matched)),
            reasoning="Deterministic fallback: matched evidence by type and keyword.",
            iteration=0,
        )

    # Formatting helpers
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
