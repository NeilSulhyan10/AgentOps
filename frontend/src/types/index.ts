export type IncidentSeverity = 'low' | 'medium' | 'high' | 'critical';
export type IncidentStatus = 'open' | 'investigating' | 'resolved' | 'closed';
export type AgentType = 'cicd' | 'kubernetes' | 'observability';
export type InvestigationStatus = 'pending' | 'running' | 'completed' | 'failed' | 'max_iterations_reached' | 'insufficient_evidence';
export type HypothesisType = 
  | 'deployment_induced_failure'
  | 'kubernetes_oom'
  | 'application_error'
  | 'configuration_error'
  | 'dependency_issue'
  | 'traffic_incident'
  | 'multi_layer_failure'
  | 'unknown';

export interface Incident {
  incident_id: string;
  title: string;
  description: string;
  severity: IncidentSeverity;
  status: IncidentStatus;
  source: string;
  service_name: string;
  namespace: string;
  started_at: string;
  detected_at: string;
  metadata: Record<string, any>;
  tags: string[];
}

export interface Evidence {
  evidence_id: string;
  investigation_id: string;
  agent_type: AgentType;
  evidence_type: string;
  description: string;
  raw_data: Record<string, any>;
  confidence: number;
  timestamp: string;
  source: string;
}

export interface AgentFinding {
  finding_id: string;
  investigation_id: string;
  agent_type: AgentType;
  hypothesis: HypothesisType;
  finding: string;
  evidence: string[];
  confidence: number;
  reasoning: string;
  timestamp: string;
  iteration: number;
}

export interface RoutingDecision {
  decision_id: string;
  investigation_id: string;
  iteration: number;
  current_hypothesis: HypothesisType | null;
  evidence_gaps: string[];
  agents_invoked: AgentType[];
  available_agents: AgentType[];
  selected_agent: AgentType;
  reasoning: string;
  timestamp: string;
}

export interface ConfidenceEntry {
  entry_id: string;
  investigation_id: string;
  iteration: number;
  agent_confidences: Record<AgentType, number>;
  overall_confidence: number;
  threshold: number;
  is_sufficient: boolean;
  timestamp: string;
}

export interface RootCauseAnalysis {
  rca_id: string;
  investigation_id: string;
  incident_id: string;
  root_cause: string;
  root_cause_type: HypothesisType;
  contributing_factors: string[];
  evidence: string[];
  agents_consulted: AgentType[];
  overall_confidence: number;
  investigation_timeline: TimelineEntry[];
  created_at: string;
}

export interface RemediationRecommendation {
  remediation_id: string;
  investigation_id: string;
  rca_id: string;
  recommendation: string;
  steps: string[];
  priority: string;
  estimated_effort: string;
  risk_level: string;
  status: string;
  created_at: string;
}

export interface InvestigationState {
  investigation_id: string;
  incident: Incident;
  incident_id: string;
  current_hypothesis: HypothesisType | null;
  evidence: Evidence[];
  agent_findings: AgentFinding[];
  agents_invoked: AgentType[];
  confidence_scores: Record<AgentType, number>;
  overall_confidence: number;
  iteration_count: number;
  max_iterations: number;
  evidence_gaps: string[];
  investigation_status: InvestigationStatus;
  root_cause: RootCauseAnalysis | null;
  remediation: RemediationRecommendation | null;
  routing_decisions: RoutingDecision[];
  confidence_history: ConfidenceEntry[];
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface InvestigationStatusResponse {
  investigation_id: string;
  incident_id: string;
  status: InvestigationStatus;
  current_hypothesis: HypothesisType | null;
  overall_confidence: number;
  iteration_count: number;
  agents_invoked: AgentType[];
  evidence_count: number;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface TimelineEntry {
  type: 'agent_finding' | 'routing_decision' | 'confidence_update';
  iteration: number;
  timestamp: string;
  agent?: AgentType;
  hypothesis?: HypothesisType;
  finding?: string;
  confidence?: number;
  evidence?: string[];
  reasoning?: string;
  selected_agent?: AgentType;
  selected_agent_reasoning?: string;
  evidence_gaps?: string[];
  agents_invoked?: AgentType[];
  overall_confidence?: number;
  agent_confidences?: Record<AgentType, number>;
  threshold?: number;
  is_sufficient?: boolean;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
}