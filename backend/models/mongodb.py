from beanie import Document
from pydantic import Field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
import uuid

from backend.models import (
    IncidentSeverity, IncidentStatus, HypothesisType,
    InvestigationStatus, EvidenceType, Evidence, AgentFinding,
    RoutingDecision, ConfidenceEntry, RootCauseAnalysis, RemediationRecommendation
)


class IncidentDoc(Document):
    incident_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    source: str
    service_name: str
    namespace: str
    started_at: datetime
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)

    class Settings:
        name = "incidents"
        use_state_management = True


class EvidenceDoc(Document):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    agent_type: str  # open string
    evidence_type: EvidenceType
    description: str
    raw_data: Dict[str, Any]
    confidence: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str

    class Settings:
        name = "evidence"
        use_state_management = True


class AgentFindingDoc(Document):
    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    agent_type: str  # open string
    hypothesis: HypothesisType
    finding: str
    evidence: List[str] = Field(default_factory=list)
    confidence: float
    reasoning: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    iteration: int = 0

    class Settings:
        name = "agent_findings"
        use_state_management = True


class RoutingDecisionDoc(Document):
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    iteration: int
    current_hypothesis: Optional[HypothesisType]
    evidence_gaps: List[str]
    agents_invoked: List[str]    # open string list
    available_agents: List[str]  # open string list
    selected_agent: str          # open string
    reasoning: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "routing_decisions"
        use_state_management = True


class ConfidenceEntryDoc(Document):
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    iteration: int
    agent_confidences: Dict[str, float]  # keyed by agent name string
    overall_confidence: float
    threshold: float
    is_sufficient: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "confidence_history"
        use_state_management = True


class RootCauseAnalysisDoc(Document):
    rca_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    incident_id: str
    root_cause: str
    root_cause_type: HypothesisType
    contributing_factors: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    agents_consulted: List[str] = Field(default_factory=list)  # open string list
    overall_confidence: float
    investigation_timeline: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "root_cause_analyses"
        use_state_management = True


class RemediationDoc(Document):
    remediation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    rca_id: str
    recommendation: str
    steps: List[str] = Field(default_factory=list)
    priority: str = "high"
    estimated_effort: str = "medium"
    risk_level: str = "low"
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "remediations"
        use_state_management = True


class InvestigationDoc(Document):
    investigation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    current_hypothesis: Optional[HypothesisType] = None
    evidence_ids: List[str] = Field(default_factory=list)
    finding_ids: List[str] = Field(default_factory=list)
    agents_invoked: List[str] = Field(default_factory=list)         # open string list
    confidence_scores: Dict[str, float] = Field(default_factory=dict)  # keyed by agent name
    overall_confidence: float = 0.0
    iteration_count: int = 0
    max_iterations: int = 5
    evidence_gaps: List[str] = Field(default_factory=list)
    investigation_status: InvestigationStatus = InvestigationStatus.PENDING
    rca_id: Optional[str] = None
    remediation_id: Optional[str] = None
    routing_decision_ids: List[str] = Field(default_factory=list)
    confidence_entry_ids: List[str] = Field(default_factory=list)
    critic_reviews: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    class Settings:
        name = "investigations"
        use_state_management = True


class ProcessedRunDoc(Document):
    """Track processed GitHub workflow run IDs to prevent duplicate incident creation."""
    run_id: int = Field(..., unique=True)
    workflow_name: str
    run_number: int
    concluded_at: datetime
    processed_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "processed_runs"
        use_state_management = True