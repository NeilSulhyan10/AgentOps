from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum
import uuid


class IncidentSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class AgentType(str, Enum):
    """
    Known built-in agent types.  The system also accepts arbitrary strings for
    dynamically discovered agents (any .md file in agents/markdown/ that is not
    a reserved name such as 'router', 'rca_synthesizer', or 'remediation_planner').
    Use AgentType constants where convenient, but do NOT rely on this enum being
    exhaustive — fields that store agent names use plain str so new agents can be
    added simply by dropping a .md file.
    """
    CICD = "cicd"
    KUBERNETES = "kubernetes"
    OBSERVABILITY = "observability"


class InvestigationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    MAX_ITERATIONS_REACHED = "max_iterations_reached"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class EvidenceType(str, Enum):
    DEPLOYMENT = "deployment"
    CODE_CHANGE = "code_change"
    CONFIG_CHANGE = "config_change"
    DEPENDENCY_CHANGE = "dependency_change"
    POD_EXIT_CODE = "pod_exit_code"
    POD_RESTART_COUNT = "pod_restart_count"
    POD_EVENT = "pod_event"
    RESOURCE_USAGE = "resource_usage"
    RESOURCE_LIMIT = "resource_limit"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    LOG = "log"
    STACK_TRACE = "stack_trace"
    CORRELATION_ID = "correlation_id"
    TRACE = "trace"
    SPAN_DURATION = "span_duration"
    ERROR_STATUS = "error_status"
    JOB_FAILURE = "job_failure"


class HypothesisType(str, Enum):
    DEPLOYMENT_INDUCED_FAILURE = "deployment_induced_failure"
    KUBERNETES_OOM = "kubernetes_oom"
    APPLICATION_ERROR = "application_error"
    CONFIGURATION_ERROR = "configuration_error"
    DEPENDENCY_ISSUE = "dependency_issue"
    TRAFFIC_INCIDENT = "traffic_incident"
    MULTI_LAYER_FAILURE = "multi_layer_failure"
    UNKNOWN = "unknown"


class Incident(BaseModel):
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

    class Config:
        use_enum_values = True


class Evidence(BaseModel):
    evidence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    agent_type: str  # open string — accepts built-in AgentType values and dynamic agents
    evidence_type: EvidenceType
    description: str
    raw_data: Dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str

    class Config:
        use_enum_values = True


class AgentFinding(BaseModel):
    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    agent_type: str  # open string — accepts built-in AgentType values and dynamic agents
    hypothesis: HypothesisType
    finding: str
    evidence: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    iteration: int = 0

    class Config:
        use_enum_values = True


class RoutingDecision(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    iteration: int
    current_hypothesis: Optional[HypothesisType]
    evidence_gaps: List[str]
    agents_invoked: List[str]      # open string list
    available_agents: List[str]    # open string list
    selected_agent: str            # open string
    reasoning: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


class ConfidenceEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    iteration: int
    agent_confidences: Dict[str, float]  # keyed by agent name string
    overall_confidence: float
    threshold: float
    is_sufficient: bool
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


class CriticReview(BaseModel):
    review_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str = ""
    round: int = 1
    verdict: Literal["confirmed", "challenged"]
    assessed_hypothesis: HypothesisType = HypothesisType.UNKNOWN
    concerns: List[str] = Field(default_factory=list)
    missing_checks: List[str] = Field(default_factory=list)
    suggested_agent: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)  # critic's confidence in the current conclusion
    reasoning: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


class RootCauseAnalysis(BaseModel):
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

    class Config:
        use_enum_values = True


class RemediationRecommendation(BaseModel):
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


class InvestigationState(BaseModel):
    investigation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident: Incident
    incident_id: str
    current_hypothesis: Optional[HypothesisType] = None
    evidence: List[Evidence] = Field(default_factory=list)
    agent_findings: List[AgentFinding] = Field(default_factory=list)
    agents_invoked: List[str] = Field(default_factory=list)       # open string list
    confidence_scores: Dict[str, float] = Field(default_factory=dict)  # keyed by agent name
    overall_confidence: float = 0.0
    iteration_count: int = 0
    max_iterations: int = 5
    evidence_gaps: List[str] = Field(default_factory=list)
    investigation_status: InvestigationStatus = InvestigationStatus.PENDING
    root_cause: Optional[RootCauseAnalysis] = None
    remediation: Optional[RemediationRecommendation] = None
    routing_decisions: List[RoutingDecision] = Field(default_factory=list)
    confidence_history: List[ConfidenceEntry] = Field(default_factory=list)
    critic_reviews: List[CriticReview] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    class Config:
        use_enum_values = True
        arbitrary_types_allowed = True


class InvestigationRequest(BaseModel):
    incident: Incident


class InvestigationResponse(BaseModel):
    investigation_id: str
    status: InvestigationStatus
    message: str


class InvestigationStatusResponse(BaseModel):
    investigation_id: str
    incident_id: str
    incident_title: str
    service_name: str = ""
    namespace: str = ""
    status: InvestigationStatus
    current_hypothesis: Optional[HypothesisType]
    overall_confidence: float
    iteration_count: int
    agents_invoked: List[str]   # open string list
    evidence_count: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        use_enum_values = True
