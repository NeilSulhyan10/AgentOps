"""The JSON shape each agent's LLM answer must have. An answer that does not fit is discarded."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from backend.models import HypothesisType


class RoutingDecisionResponse(BaseModel):
    selected_agent: str  # open string — matches agent md file stem
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)


class AgentAnalysisResponse(BaseModel):
    finding: str
    hypothesis: HypothesisType
    evidence: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class CriticResponse(BaseModel):
    verdict: Literal["confirmed", "challenged"]
    hypothesis: HypothesisType = HypothesisType.UNKNOWN
    concerns: List[str] = Field(default_factory=list)
    missing_checks: List[str] = Field(default_factory=list)
    suggested_agent: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


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