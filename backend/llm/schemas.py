from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from backend.models import AgentType, HypothesisType, AgentFinding, Evidence, RoutingDecision, RootCauseAnalysis, RemediationRecommendation, EvidenceType


class LLMRequest(BaseModel):
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4096
    metadata: Dict[str, Any] = {}


class LLMResponse(BaseModel):
    content: str
    tokens_used: int = 0
    model: str = ""
    metadata: Dict[str, Any] = {}


class RoutingDecisionResponse(BaseModel):
    selected_agent: AgentType
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class AgentAnalysisResponse(BaseModel):
    finding: str
    hypothesis: HypothesisType
    evidence: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class RCAResponse(BaseModel):
    root_cause: str
    root_cause_type: HypothesisType
    contributing_factors: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class RemediationResponse(BaseModel):
    recommendation: str
    steps: List[str] = Field(default_factory=list)
    priority: str = "high"
    estimated_effort: str = "medium"
    risk_level: str = "low"