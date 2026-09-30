"""
Baseline fixed-workflow investigation system for comparison with adaptive orchestrator.

This system always runs all three agents in a fixed order (CICD -> Kubernetes -> Observability)
regardless of the incident characteristics, providing a baseline for evaluation.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from backend.models import (
    Incident,
    InvestigationState,
    AgentFinding,
    RoutingDecision,
    ConfidenceEntry,
    RootCauseAnalysis,
    RemediationRecommendation,
    AgentType,
    HypothesisType,
    InvestigationStatus,
    Evidence,
    EvidenceType,
)
from backend.agents.cicd.agent import CICDAgent
from backend.agents.kubernetes.agent import KubernetesAgent
from backend.agents.observability.agent import ObservabilityAgent
from backend.orchestrator.confidence import (
    calculate_overall_confidence,
    synthesize_rca,
    generate_remediation,
)
from backend.tools.data_access import get_cicd_evidence, get_kubernetes_evidence, get_observability_evidence


class FixedWorkflowInvestigator:
    """
    Fixed workflow investigator that always invokes all agents in a predetermined order.
    """
    
    def __init__(self):
        self.agents = {
            AgentType.CICD: CICDAgent(),
            AgentType.KUBERNETES: KubernetesAgent(),
            AgentType.OBSERVABILITY: ObservabilityAgent(),
        }
        self.agent_order = [AgentType.CICD, AgentType.KUBERNETES, AgentType.OBSERVABILITY]
    
    def investigate(self, incident: Incident) -> InvestigationState:
        """
        Run investigation using fixed workflow.
        """
        # Load evidence
        cicd_evidence = get_cicd_evidence(incident)
        k8s_evidence = get_kubernetes_evidence(incident)
        obs_evidence = get_observability_evidence(incident)
        all_evidence = cicd_evidence + k8s_evidence + obs_evidence
        
        # Create initial state
        investigation = InvestigationState(
            incident=incident,
            incident_id=incident.incident_id,
            max_iterations=3,
            investigation_status=InvestigationStatus.RUNNING,
        )
        investigation.evidence = all_evidence
        
        # Run fixed agent sequence
        for i, agent_type in enumerate(self.agent_order):
            agent = self.agents[agent_type]
            finding = agent.investigate(incident, all_evidence)
            
            finding.investigation_id = investigation.investigation_id
            finding.iteration = i
            finding.timestamp = datetime.utcnow()
            
            investigation.agent_findings.append(finding)
            investigation.agents_invoked.append(agent_type)
            investigation.confidence_scores[agent_type] = finding.confidence
            
            # Add routing decision for tracking
            routing = RoutingDecision(
                investigation_id=investigation.investigation_id,
                iteration=i,
                current_hypothesis=investigation.current_hypothesis,
                evidence_gaps=investigation.evidence_gaps,
                agents_invoked=investigation.agents_invoked[:-1],
                available_agents=[a for a in AgentType if a not in investigation.agents_invoked],
                selected_agent=agent_type,
                reasoning=f"Fixed workflow: invoking {agent_type.value} agent (step {i+1}/3)"
            )
            investigation.routing_decisions.append(routing)
        
        investigation.iteration_count = len(self.agent_order)
        
        # Calculate overall confidence
        overall_confidence = calculate_overall_confidence(investigation.confidence_scores)
        investigation.overall_confidence = overall_confidence
        
        # Add confidence entry
        confidence_entry = ConfidenceEntry(
            investigation_id=investigation.investigation_id,
            iteration=investigation.iteration_count,
            agent_confidences=investigation.confidence_scores.copy(),
            overall_confidence=overall_confidence,
            threshold=0.75,
            is_sufficient=overall_confidence >= 0.75
        )
        investigation.confidence_history.append(confidence_entry)
        
        # Generate RCA
        investigation.root_cause = synthesize_rca(investigation)
        
        # Generate remediation
        investigation.remediation = generate_remediation(investigation.root_cause)
        
        investigation.investigation_status = InvestigationStatus.COMPLETED
        investigation.completed_at = datetime.utcnow()
        investigation.updated_at = datetime.utcnow()
        
        return investigation


def run_fixed_workflow_investigation(incident_id: str) -> InvestigationState:
    """
    Run fixed workflow investigation for a given incident ID.
    """
    # Load incident
    from backend.tools.data_access import DataLoader
    loader = DataLoader()
    incident_data = loader.load_incident_data(incident_id)
    
    if not incident_data:
        raise ValueError(f"Incident {incident_id} not found")
    
    incident = Incident(**incident_data)
    investigator = FixedWorkflowInvestigator()
    return investigator.investigate(incident)