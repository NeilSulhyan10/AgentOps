// Shapes returned by GET /api/investigations/{id}/flow and GET /api/agents.

export type FlowStatus = 'ok' | 'warning' | 'error' | 'skipped'

export interface FlowEvent {
  event: string
  ts?: string
  [key: string]: any
}

export interface FlowStep {
  index: number
  node: string
  title: string
  status: FlowStatus
  notes: string[]
  duration_ms: number | null
  events: FlowEvent[]
}

export interface PipelineNode {
  id: string
  purpose: string
  help: string
  status: FlowStatus
  visits: number
  summary: string
}

export interface PipelineEdge {
  source: string
  target: string
  taken: boolean
}

export interface LayerState {
  key: string
  name: string
  watches: string
  agent: string
  status: 'root' | 'affected' | 'clear' | 'not_checked'
  detail: string
}

export interface FlowTrace {
  investigation_id: string
  incident_id: string
  title: string
  service: string
  engine: string
  fault: string
  final_status: string
  root_cause_type: string
  confidence: number
  headline: string
  worst_status: FlowStatus
  steps: FlowStep[]
  pipeline: { nodes: PipelineNode[]; edges: PipelineEdge[] }
  layers: LayerState[]
  layer_edges: { source: string; target: string }[]
  findings: Record<string, { hypothesis: string; confidence: number; grounded: boolean }>
  confidence_breakdown: ConfidenceBreakdown | Record<string, never>
  spawned: Record<string, { layer: string; hypothesis: string; description: string; keywords: string[]; reason: string }>
}

export interface AgentInfo {
  name: string
  description: string
  layer: string
  hypothesis: string
  evidence_types: string[]
  keywords: string[]
  origin: string
}

export interface Spawnable {
  name: string
  title: string
  layer: string
  looks_for: string
  keywords: string[]
}

export interface FindingScore {
  agent: string
  hypothesis: string
  reported: number
  strength: number
  coverage: number
  grounding: number
  score: number
}

export interface ConfidenceBreakdown {
  hypothesis: string
  reason: string
  base: number
  corroboration: number
  contradiction: number
  open_gaps: number
  critic: number
  overall: number
  findings: FindingScore[]
  formula: string
}
