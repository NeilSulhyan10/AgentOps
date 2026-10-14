"""
Agent Runner

Generic agent execution runtime that loads agent definitions from Markdown
and executes them using the LLM provider with structured output parsing.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Type

from backend.llm import get_llm_provider, LLMRequest
from backend.llm.schemas import AgentAnalysisResponse, RoutingDecisionResponse, RCAResponse, RemediationResponse
from backend.models import AgentType, HypothesisType, Evidence, Incident, AgentFinding, RootCauseAnalysis, RemediationRecommendation

logger = logging.getLogger(__name__)


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
        previous_findings: List[AgentFinding] = None
    ) -> AgentFinding:
        """Run a specialist analysis agent (CICD, Kubernetes, Observability)."""
        
        agent_type_map = {
            "cicd_analyzer": AgentType.CICD,
            "kubernetes_analyzer": AgentType.KUBERNETES,
            "observability_analyzer": AgentType.OBSERVABILITY,
        }
        
        agent_type = agent_type_map.get(agent_name)
        if not agent_type:
            raise ValueError(f"Unknown analysis agent: {agent_name}")
        
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
        
        output_schema = """{
  "hypothesis": "deployment_induced_failure|kubernetes_oom|traffic_incident|configuration_error|dependency_issue|application_error|multi_layer_failure|unknown",
  "finding": "Human-readable finding description",
  "evidence": ["exact evidence_id values from the supplied evidence"],
  "confidence": 0.85,
  "reasoning": "Combined reasoning from all matched evidence"
}"""
        
        prompt = self._build_prompt(agent_name, input_data, output_schema)
        
        system_prompt = f"You are a {agent_type.value} specialist investigating a DevOps incident. Analyze the evidence and provide a structured finding. In the evidence array, include only exact evidence_id values shown in the supplied evidence; use an empty array if none support the finding. Respond with JSON only."
        
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
                agent_type=agent_type,
                hypothesis=analysis_data.hypothesis,
                finding=analysis_data.finding,
                evidence=analysis_data.evidence,
                confidence=analysis_data.confidence,
                reasoning=analysis_data.reasoning,
                iteration=0  # Set by caller
            )
            logger.info(f"Agent {agent_name} completed: {finding.finding[:100]}")
            return finding
        except Exception as e:
            logger.warning(f"LLM parsing failed for {agent_name}, using deterministic fallback: {e}")
            return await self._run_deterministic_fallback(agent_type, incident, evidence)
    
    async def run_router_agent(
        self,
        incident: Incident,
        current_hypothesis: Optional[HypothesisType],
        evidence_gaps: List[str],
        agents_invoked: List[AgentType],
        available_agents: List[AgentType],
        evidence_summary: str,
        findings_summary: str
    ) -> tuple[AgentType, str]:
        """Run the router agent to select next specialist."""
        
        input_data = {
            "incident": {
                "title": incident.title,
                "description": incident.description,
                "service_name": incident.service_name,
                "namespace": incident.namespace,
            },
            "current_hypothesis": current_hypothesis.value if current_hypothesis else "UNKNOWN",
            "evidence_gaps": evidence_gaps,
            "agents_invoked": [a.value for a in agents_invoked],
            "available_agents": [a.value for a in available_agents],
            "evidence_collected": evidence_summary,
            "agent_findings": findings_summary,
        }
        
        output_schema = """{
  "selected_agent": "cicd|kubernetes|observability",
  "reasoning": "Detailed explanation of why this agent was selected",
  "confidence": 0.85
}"""
        
        prompt = self._build_prompt("router", input_data, output_schema)
        
        system_prompt = "You are an expert DevOps incident investigator. Select the most relevant specialist agent to investigate next based on the evidence gaps and current hypothesis. Respond with JSON only."
        
        response = await self.llm.generate(LLMRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=1024,
            metadata={"task": "routing", "incident_id": incident.incident_id},
        ))
        
        try:
            routing_data = RoutingDecisionResponse.model_validate_json(response.content)
            return routing_data.selected_agent, routing_data.reasoning
        except Exception as e:
            logger.warning(f"Router LLM parsing failed, using fallback: {e}")
            return available_agents[0] if available_agents else AgentType.CICD, "Fallback to deterministic routing"
    
    async def run_rca_agent(
        self,
        incident: Incident,
        agent_findings: List[AgentFinding],
        evidence: List[Evidence],
        routing_decisions: List,
        confidence_history: List
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
            from backend.orchestrator.confidence import synthesize_rca
            # Create minimal investigation state for fallback
            class MockState:
                pass
            state = MockState()
            state.agent_findings = agent_findings
            state.incident_id = incident.incident_id
            state.investigation_id = ""
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
            # Create minimal RCA for fallback
            class MockRCA:
                pass
            rca = MockRCA()
            rca.root_cause_type = root_cause_type
            return generate_remediation(rca)
    
    async def _run_deterministic_fallback(
        self,
        agent_type: AgentType,
        incident: Incident,
        evidence: List[Evidence]
    ) -> AgentFinding:
        """Run deterministic agent as fallback."""
        from backend.agents.cicd.agent import CICDAgent
        from backend.agents.kubernetes.agent import KubernetesAgent
        from backend.agents.observability.agent import ObservabilityAgent
        
        agents = {
            AgentType.CICD: CICDAgent(),
            AgentType.KUBERNETES: KubernetesAgent(),
            AgentType.OBSERVABILITY: ObservabilityAgent()
        }
        
        agent = agents[agent_type]
        return agent.investigate(incident, evidence)
    
    # Formatting helpers
    def _format_evidence(self, evidence: List[Evidence]) -> str:
        if not evidence:
            return "No evidence collected yet."
        lines = []
        for ev in evidence[-10:]:
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
