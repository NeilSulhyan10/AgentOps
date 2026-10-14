import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { investigationApi } from '../api/client'
import { useInvestigationRealtime } from '../hooks/useInvestigationWS'
import type { Evidence, InvestigationState, TimelineEntry, AgentType } from '../types'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/Card'
import { Badge } from './ui/Badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/Tabs'
import { Progress } from './ui/Progress'
import { Button } from './ui/Button'
import { formatDate, formatIncidentId, getStatusColor, getAgentColor, formatConfidence, getConfidenceColor, truncate } from '../utils/helpers'
import { 
  AlertTriangle, 
  Brain, 
  ArrowRight,
  ChevronRight,
  FileText,
  Wrench,
  Zap,
  BarChart2,
  Loader2,
  Wifi,
  WifiOff,
  X,
  Copy,
  Check
} from 'lucide-react'
import { cn } from '../utils/helpers'
import { ConfidenceChart } from './ConfidenceChart'

const agentLabels: Record<AgentType, string> = {
  cicd: 'CI/CD',
  kubernetes: 'Kubernetes',
  observability: 'Observability'
}

export function InvestigationDetail() {
  const { investigationId } = useParams<{ investigationId: string }>()
  const navigate = useNavigate()
  const [baseInvestigation, setInvestigation] = useState<InvestigationState | null>(null)
  const [timeline, setTimeline] = useState<TimelineEntry[]>([])
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  // Real-time WebSocket connection
  const { 
    connected, 
    agentThinking, 
    routingDecision, 
    agentFinding, 
    progress: wsProgress,
    liveEvents,
    getRealtimeInvestigation 
  } = useInvestigationRealtime(investigationId)

  useEffect(() => {
    if (!investigationId) return

    const fetchData = async () => {
      try {
        setLoading(true)
        const [invData, timelineData] = await Promise.all([
          investigationApi.get(investigationId),
          investigationApi.getTimeline(investigationId)
        ])
        setInvestigation(invData)
        setTimeline(timelineData.timeline)
        setError(null)
      } catch (err) {
        setError('Failed to load investigation')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [investigationId])

  // Merge real-time data with base investigation
  const realtimeInvestigation = useMemo(() => {
    if (!baseInvestigation) return null
    return getRealtimeInvestigation(baseInvestigation)
  }, [baseInvestigation, getRealtimeInvestigation])

  // Use real-time investigation if available, otherwise fall back to base
  const displayInvestigation = realtimeInvestigation || baseInvestigation

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    )
  }

  if (error || !displayInvestigation) {
    return (
      <Card className="border-red-200 dark:border-red-800 max-w-2xl mx-auto">
        <CardContent className="pt-6 text-center">
          <AlertTriangle className="h-12 w-12 text-red-600 dark:text-red-400 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-dark-900 dark:text-dark-100 mb-2">Investigation Not Found</h3>
          <p className="text-dark-500 dark:text-dark-400 mb-4">{error || 'Unable to load investigation details'}</p>
          <Button onClick={() => navigate('/')}>Back to Incidents</Button>
        </CardContent>
      </Card>
    )
  }

// Type guard to narrow the type
  const investigation = displayInvestigation as InvestigationState | null;
  if (!investigation) return null;

  // TypeScript knows investigation is non-null here
  const inv = investigation;
  const confidenceThreshold = inv.confidence_history.length
    ? inv.confidence_history[inv.confidence_history.length - 1].threshold
    : 0.75;

  // Use inv for the rest of the component
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark-900 dark:text-dark-100">
            {inv.incident.title || formatIncidentId(inv.incident_id)}
          </h1>
          <p className="text-dark-500 dark:text-dark-400" title={inv.incident_id}>Incident: {formatIncidentId(inv.incident_id)}</p>
        </div>
        <div className="flex items-center gap-3">
          {/* WebSocket Connection Status */}
          <div className="flex items-center gap-2 px-2 py-1 rounded-lg bg-dark-100 dark:bg-dark-800" title={connected ? 'Live updates connected' : 'Live updates disconnected; investigation details can still load'}>
            {connected ? (
              <>
                <Wifi className="h-4 w-4 text-green-500" />
                <span className="text-xs text-green-600 dark:text-green-400 font-medium">Live</span>
              </>
            ) : (
              <>
                <WifiOff className="h-4 w-4 text-red-500" />
                <span className="text-xs text-red-600 dark:text-red-400 font-medium">Offline</span>
              </>
            )}
          </div>
          
          {/* Real-time Agent Status */}
          {agentThinking && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary-50 dark:bg-primary-900/30 border border-primary-200 dark:border-primary-800 animate-pulse">
              <Loader2 className="h-4 w-4 text-primary-600 dark:text-primary-400" />
              <span className="text-sm font-medium text-primary-700 dark:text-primary-300">
                {agentLabels[agentThinking.agent_type as AgentType]}: {agentThinking.status === 'thinking' ? 'Analyzing...' : agentThinking.status === 'started' ? 'Starting...' : 'Completed'}
              </span>
            </div>
          )}
          
          <Badge className={cn('text-sm', getStatusColor(inv.investigation_status))}>
            {inv.investigation_status.replace('_', ' ')}
          </Badge>
          <Button variant="ghost" onClick={() => navigate('/')}>
            Back to List
          </Button>
        </div>
      </div>

      <Card className="border-primary-200 dark:border-primary-900">
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle className="text-base">Live investigation activity</CardTitle>
            <CardDescription>Recent routing, agent, and progress updates</CardDescription>
          </div>
          <Badge variant={connected ? 'success' : 'secondary'}>{connected ? 'Connected' : 'Reconnecting'}</Badge>
        </CardHeader>
        <CardContent>
          {liveEvents.length === 0 ? (
            <p className="text-sm text-dark-500 dark:text-dark-400">
              {connected ? 'Connected. Waiting for the next investigation step…' : 'Live updates are unavailable. Saved investigation details remain below.'}
            </p>
          ) : (
            <ol className="max-h-64 space-y-3 overflow-y-auto">
              {liveEvents.map((event, index) => (
                <li key={`${event.timestamp}-${index}`} className="flex items-start gap-3 border-l-2 border-primary-200 pl-3 dark:border-primary-800">
                  <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-primary-500" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-dark-800 dark:text-dark-200">{describeLiveEvent(event)}</p>
                    <time className="text-xs text-dark-400">{formatDate(event.timestamp)}</time>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Overall Confidence</CardTitle>
            <CardDescription>Strongest agent finding backed by cited evidence</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-center">
              <div className="relative w-32 h-32 mx-auto mb-4">
                <svg className="w-full h-full transform -rotate-90">
                  <circle
                    cx="64"
                    cy="64"
                    r="58"
                    stroke="currentColor"
                    strokeWidth="8"
                    fill="none"
                    className="text-dark-200 dark:text-dark-700"
                  />
                  <circle
                    cx="64"
                    cy="64"
                    r="58"
                    stroke="currentColor"
                    strokeWidth="8"
                    strokeDasharray={364.4}
                    strokeDashoffset={364.4 - (364.4 * inv.overall_confidence)}
                    strokeLinecap="round"
                    fill="none"
                    className={cn('transition-all duration-1000', getConfidenceColor(inv.overall_confidence))}
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className={cn('text-3xl font-bold', getConfidenceColor(inv.overall_confidence))}>
                    {formatConfidence(inv.overall_confidence)}
                  </span>
                </div>
              </div>
              <Progress value={inv.overall_confidence * 100} className="w-full max-w-xs mx-auto" />
              <p className="mt-2 text-sm text-dark-500">
                Threshold: {Math.round(confidenceThreshold * 100)}% • {inv.investigation_status === 'completed' ? 'Threshold met' : 'Threshold not met'}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Agents Invoked</CardTitle>
            <CardDescription>{inv.agents_invoked.length} of 3 agents</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {['cicd', 'kubernetes', 'observability'].map((agent) => {
                const invoked = inv.agents_invoked.includes(agent as AgentType)
                const confidence = inv.confidence_scores[agent as AgentType]
                const isCurrentlyRunning = agentThinking?.agent_type === agent && agentThinking.status === 'thinking'
                return (
                  <div
                    key={agent}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all',
                      isCurrentlyRunning
                        ? 'ring-2 ring-primary-500 animate-pulse'
                        : invoked
                        ? getAgentColor(agent).replace('bg-', 'bg-').replace('text-', 'text-')
                        : 'bg-dark-100 text-dark-400 dark:bg-dark-800 dark:text-dark-500'
                    )}
                  >
                    <span className={cn(getAgentColor(agent).replace('bg-', 'text-').replace('text-', 'text-'))}>
                      {agentLabels[agent as AgentType]}
                    </span>
                    {isCurrentlyRunning && <Loader2 className="h-3 w-3 text-primary-500 animate-spin" />}
                    {invoked && confidence && (
                      <span className={cn('font-mono text-xs', getConfidenceColor(confidence))}>
                        {formatConfidence(confidence)}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
            
            {/* Real-time Progress Bar */}
            {wsProgress && (
              <div className="mt-4">
                <div className="flex justify-between text-xs text-dark-500 mb-1">
                  <span>Iteration {wsProgress.iteration} of {wsProgress.max_iterations}</span>
                  <span>{wsProgress.progress_percent}% complete</span>
                </div>
                <Progress value={wsProgress.progress_percent} className="h-2" />
                <p className="text-xs text-dark-500 mt-1">Confidence: {formatConfidence(wsProgress.overall_confidence)}</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Current Hypothesis</CardTitle>
            <CardDescription>Primary investigation direction</CardDescription>
          </CardHeader>
          <CardContent>
            {inv.current_hypothesis ? (
              <Badge variant="default" className="text-base px-3 py-1">
                {inv.current_hypothesis.replace(/_/g, ' ')}
              </Badge>
            ) : (
              <span className="text-dark-500 dark:text-dark-400">No hypothesis yet</span>
            )}
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="confidence">
            <BarChart2 className="h-4 w-4 mr-2" />
            Confidence
          </TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="rca">Root Cause</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Investigation Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="text-sm text-dark-500 dark:text-dark-400">Investigation ID</p>
                    <p className="font-mono text-sm">{inv.investigation_id}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-500 dark:text-dark-400">Incident ID</p>
                    <p className="font-mono text-sm" title={inv.incident_id}>{formatIncidentId(inv.incident_id)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-500 dark:text-dark-400">Started</p>
                    <p className="font-mono text-sm">{formatDate(inv.created_at)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-500 dark:text-dark-400">Completed</p>
                    <p className="font-mono text-sm">{inv.completed_at ? formatDate(inv.completed_at) : 'In progress'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-500 dark:text-dark-400">Iterations</p>
                    <p className="font-mono text-sm">{inv.iteration_count} / {inv.max_iterations}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-500 dark:text-dark-400">Evidence Collected</p>
                    <p className="font-mono text-sm">{inv.evidence.length}</p>
                  </div>
                </div>
                
                {/* Real-time Routing Decision */}
                {routingDecision && (
                  <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg animate-pulse">
                    <div className="flex items-center gap-2 mb-2">
                      <Brain className="h-5 w-5 text-blue-500" />
                      <span className="font-medium text-blue-700 dark:text-blue-300">Routing Decision (Iteration {routingDecision.iteration})</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className={cn(getAgentColor(routingDecision.selected_agent))}>
                        {agentLabels[routingDecision.selected_agent as AgentType]}
                      </Badge>
                      <span className="text-sm text-blue-700 dark:text-blue-300 font-medium">Selected</span>
                    </div>
                    <p className="text-sm text-blue-600 dark:text-blue-400 mt-2">{routingDecision.reasoning}</p>
                  </div>
                )}
              
                {/* Real-time Agent Finding */}
                {agentFinding && (
                  <div className="mt-4 p-4 bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 rounded-lg">
                    <div className="flex items-center gap-2 mb-2">
<Badge className={cn(getAgentColor(agentFinding.agent_type as AgentType))}>
                      {agentLabels[agentFinding.agent_type as AgentType]}
                    </Badge>
                      <span className="font-medium text-purple-700 dark:text-purple-300">Agent Finding (Just Completed)</span>
                    </div>
                    <div className="grid gap-2 text-sm">
                      <div>
                        <span className="text-purple-700 dark:text-purple-300 font-medium">Hypothesis: </span>
                        <span className="text-purple-600 dark:text-purple-400">{agentFinding.finding.hypothesis.replace(/_/g, ' ')}</span>
                      </div>
                      <div>
                        <span className="text-purple-700 dark:text-purple-300 font-medium">Confidence: </span>
                        <span className={cn('font-mono', getConfidenceColor(agentFinding.finding.confidence))}>
                          {formatConfidence(agentFinding.finding.confidence)}
                        </span>
                      </div>
                      <div>
                        <span className="text-purple-700 dark:text-purple-300 font-medium">Finding: </span>
                        <span className="text-purple-600 dark:text-purple-400">{truncate(agentFinding.finding.finding, 100)}</span>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Agent Findings</CardTitle>
              </CardHeader>
              <CardContent>
                {inv.agent_findings.length === 0 ? (
                  <p className="text-dark-500 dark:text-dark-400 text-center py-8">No agent findings yet</p>
                ) : (
                  <div className="space-y-4">
                    {inv.agent_findings.map((finding) => (
                      <Card key={finding.finding_id} className="border-l-4" style={{ borderColor: getAgentColor(finding.agent_type).replace('bg-', '').replace('text-', '') }}>
                        <CardContent className="pt-4">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <Badge className={cn(getAgentColor(finding.agent_type))}>
                                  {agentLabels[finding.agent_type]}
                                </Badge>
                                <Badge variant="secondary" className="text-xs">
                                  {finding.hypothesis.replace(/_/g, ' ')}
                                </Badge>
                                <span className={cn('font-mono text-sm', getConfidenceColor(finding.confidence))}>
                                  {formatConfidence(finding.confidence)}
                                </span>
                              </div>
                              <p className="text-dark-900 dark:text-dark-100 mb-2">{finding.finding}</p>
                              <p className="text-sm text-dark-500 dark:text-dark-400">{finding.reasoning}</p>
                              {finding.evidence.length > 0 && (
                                <div className="mt-2 flex flex-wrap gap-1">
                                  {finding.evidence.map((ev, i) => (
                                    <Badge key={i} variant="outline" className="text-xs">
                                      {truncate(ev, 40)}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="confidence">
          <ConfidenceChart confidenceHistory={inv.confidence_history} />
        </TabsContent>

        <TabsContent value="timeline">
          <Card>
            <CardHeader>
              <CardTitle>Investigation Timeline</CardTitle>
              <CardDescription>Complete audit trail of all investigation steps</CardDescription>
            </CardHeader>
            <CardContent>
              {timeline.length === 0 ? (
                <p className="text-dark-500 dark:text-dark-400 text-center py-8">No timeline events</p>
              ) : (
                <div className="space-y-4">
                  {timeline.map((event, index) => (
                    <div key={index} className="flex gap-4">
                      <div className="flex flex-col items-center">
                        <div className={cn(
                          'w-3 h-3 rounded-full border-2',
                          event.type === 'agent_finding' ? 'bg-purple-500' :
                          event.type === 'routing_decision' ? 'bg-blue-500' :
                          'bg-green-500'
                        )} />
                        {index < timeline.length - 1 && (
                          <div className="w-0.5 h-full bg-dark-200 dark:bg-dark-700 mt-1" />
                        )}
                      </div>
                      <div className="flex-1 pt-1">
                        <div className="flex items-center gap-2 mb-1">
                          <>
                            {event.type === 'agent_finding' && (
                              <>
                                <span className={cn(getAgentColor(event.agent!))}>
                                  {event.agent ? agentLabels[event.agent] : 'Agent'}
                                </span>
                                <ArrowRight className="h-4 w-4 text-dark-400" />
                                <span className="text-dark-500 dark:text-dark-400">{event.hypothesis?.replace(/_/g, ' ')}</span>
                              </>
                            )}
                            {event.type === 'routing_decision' && (
                              <>
                                <Brain className="h-4 w-4 text-blue-500" />
                                <span className="text-dark-900 dark:text-dark-100">Routed to </span>
                                <span className={cn(getAgentColor(event.selected_agent!))}>{agentLabels[event.selected_agent!]}</span>
                              </>
                            )}
                            {event.type === 'confidence_update' && (
                              <>
                                <Zap className="h-4 w-4 text-green-500" />
                                <span className="text-dark-900 dark:text-dark-100">Confidence: </span>
                                <span className={cn('font-mono', getConfidenceColor(event.overall_confidence!))}>
                                  {formatConfidence(event.overall_confidence!)}
                                </span>
                                {event.is_sufficient && <Badge variant="success" className="text-xs">Threshold met</Badge>}
                              </>
                            )}
                          </>
                        </div>
                          {event.type === 'agent_finding' && event.finding && (
                            <p className="text-sm text-dark-600 dark:text-dark-300 ml-6">{event.finding}</p>
                          )}
                          {event.type === 'routing_decision' && event.selected_agent_reasoning && (
                            <p className="text-sm text-dark-500 dark:text-dark-400 ml-6">{event.selected_agent_reasoning}</p>
                          )}
                          {event.type === 'confidence_update' && event.agent_confidences && (
                            <div className="flex gap-2 ml-6 mt-1">
                              {Object.entries(event.agent_confidences).map(([agent, conf]) => (
                                <Badge key={agent} variant="outline" className="text-xs">
                                  {agent}: {formatConfidence(conf)}
                                </Badge>
                              ))}
                            </div>
                          )}
                          <p className="text-xs text-dark-400 mt-1 ml-6">{formatDate(event.timestamp)}</p>
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="evidence">
          <Card>
            <CardHeader>
              <CardTitle>Collected Evidence</CardTitle>
              <CardDescription>All evidence gathered during investigation</CardDescription>
            </CardHeader>
            <CardContent>
              {inv.evidence.length === 0 ? (
                <p className="text-dark-500 dark:text-dark-400 text-center py-8">No evidence collected yet</p>
              ) : (
                <div className="space-y-3">
                  {inv.evidence.map((ev) => (
                    <Card key={ev.evidence_id} className="border-l-4" style={{ borderColor: getAgentColor(ev.agent_type).replace('bg-', '').replace('text-', '') }}>
                      <CardContent className="pt-3 pb-3">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <Badge className={cn(getAgentColor(ev.agent_type))}>
                                {agentLabels[ev.agent_type]}
                              </Badge>
                              <Badge variant="outline" className="text-xs capitalize">
                                {ev.evidence_type.replace(/_/g, ' ')}
                              </Badge>
                              <span className={cn('font-mono text-xs', getConfidenceColor(ev.confidence))}>
                                {formatConfidence(ev.confidence)}
                              </span>
                            </div>
                            <p className="text-dark-900 dark:text-dark-100">{ev.description}</p>
                          </div>
                          <Button variant="outline" size="sm" onClick={() => setSelectedEvidence(ev)}>
                            View Raw Data
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="rca">
          {inv.root_cause ? (
            <div className="space-y-6">
              <Card className="border-l-4 border-red-500">
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                    What caused the incident?
                  </CardTitle>
                    <CardDescription>A plain-language explanation based on the evidence collected</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                    <div className="space-y-2 text-dark-900 dark:text-dark-100">
                      {inv.root_cause.root_cause.split(/\n+/).filter(Boolean).map((line, index) => {
                        const section = line.match(/^(What happened|Why it happened|Why it is likely|Why it is unclear|Analogy):\s*(.*)$/i)
                        return (
                          <p key={index}>
                            {section ? <><strong>{section[1]}:</strong> {section[2]}</> : line}
                          </p>
                        )
                      })}
                    </div>
                  </div>
                  <div className="grid gap-4 md:grid-cols-3">
                    <div>
                      <p className="text-sm text-dark-500 dark:text-dark-400">Main cause</p>
                      <p className="font-medium">{friendlyRcaType(inv.root_cause.root_cause_type)}</p>
                    </div>
                    <div>
                      <p className="text-sm text-dark-500 dark:text-dark-400">Overall Confidence</p>
                      <p className={cn('font-mono text-lg font-bold', getConfidenceColor(inv.root_cause.overall_confidence))}>
                        {formatConfidence(inv.root_cause.overall_confidence)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-dark-500 dark:text-dark-400">Agents Consulted</p>
                      <p className="font-medium">{inv.root_cause.agents_consulted.length}</p>
                    </div>
                  </div>
                  {inv.root_cause.contributing_factors.length > 0 && (
                    <div>
                      <h4 className="font-medium mb-2">Contributing Factors</h4>
                      <ul className="space-y-1">
                        {inv.root_cause.contributing_factors.map((factor, i) => (
                          <li key={i} className="flex items-center gap-2 text-sm text-dark-600 dark:text-dark-300">
                            <ChevronRight className="h-4 w-4 text-dark-400" />
                            {factor}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {inv.root_cause.evidence.length > 0 && (
                    <div>
                      <h4 className="font-medium mb-2">Supporting Evidence</h4>
                      <div className="flex flex-wrap gap-2">
                        {inv.root_cause.evidence.map((ev, i) => (
                          <Badge key={i} variant="outline" className="text-xs">
                            {truncate(ev, 50)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {inv.remediation && (
                <Card className="border-l-4 border-green-500">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Wrench className="h-5 w-5 text-green-500" />
                      Remediation Recommendation
                    </CardTitle>
                    <CardDescription>Recommended steps to resolve the incident</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                      <p className="text-dark-900 dark:text-dark-100">{inv.remediation.recommendation}</p>
                    </div>
                    <div>
                      <h4 className="font-medium mb-2">Remediation Steps</h4>
                      <ol className="space-y-2">
                        {inv.remediation.steps.map((step, i) => (
                          <li key={i} className="flex items-start gap-3 text-dark-600 dark:text-dark-300">
                            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary-100 dark:bg-primary-900/30 text-primary-600 dark:text-primary-400 text-xs font-medium flex items-center justify-center">
                              {i + 1}
                            </span>
                            <span>{step}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                    <div className="grid gap-4 md:grid-cols-3">
                      <div>
                        <p className="text-sm text-dark-500 dark:text-dark-400">Priority</p>
                        <Badge variant={inv.remediation.priority === 'high' ? 'destructive' : 'default'}>
                          {inv.remediation.priority}
                        </Badge>
                      </div>
                      <div>
                        <p className="text-sm text-dark-500 dark:text-dark-400">Effort</p>
                        <Badge variant="secondary">{inv.remediation.estimated_effort}</Badge>
                      </div>
                      <div>
                        <p className="text-sm text-dark-500 dark:text-dark-400">Risk Level</p>
                        <Badge variant={inv.remediation.risk_level === 'high' ? 'destructive' : 'secondary'}>
                          {inv.remediation.risk_level}
                        </Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          ) : (
            <Card>
              <CardContent className="pt-12 text-center">
                <FileText className="h-12 w-12 text-dark-300 dark:text-dark-600 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-dark-900 dark:text-dark-100 mb-2">Root Cause Analysis Not Available</h3>
                <p className="text-dark-500 dark:text-dark-400">The investigation has not yet generated a root cause analysis.</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
      {selectedEvidence && <RawDataDialog evidence={selectedEvidence} onClose={() => setSelectedEvidence(null)} />}
    </div>
  )
}

function describeLiveEvent(event: { update_type: string; data: Record<string, any> }): string {
  const agent = event.data.agent_type
    ? agentLabels[event.data.agent_type as AgentType] || event.data.agent_type
    : 'Agent'

  switch (event.update_type) {
    case 'status_change':
      return `Investigation status changed to ${String(event.data.status || 'updated').replace(/_/g, ' ')}`
    case 'progress':
      return `Iteration ${event.data.iteration} of ${event.data.max_iterations} · confidence ${formatConfidence(event.data.overall_confidence || 0)}`
    case 'routing_decision': {
      const selected = agentLabels[event.data.selected_agent as AgentType] || event.data.selected_agent || 'an agent'
      return `Router selected ${selected}${event.data.reasoning ? ` — ${event.data.reasoning}` : ''}`
    }
    case 'agent_thinking':
      return `${agent} ${event.data.status === 'completed' ? 'finished analyzing' : 'is analyzing'}`
    case 'agent_finding': {
      const finding = event.data.finding || {}
      const hypothesis = finding.hypothesis ? `: ${String(finding.hypothesis).replace(/_/g, ' ')}` : ''
      return `${agent} submitted a finding${hypothesis}`
    }
    default:
      return event.update_type.replace(/_/g, ' ')
  }
}

function friendlyRcaType(type: string): string {
  const labels: Record<string, string> = {
    deployment_induced_failure: 'A recent software change',
    kubernetes_oom: 'The service ran out of memory',
    traffic_incident: 'A sudden change in incoming requests',
    configuration_error: 'A problem with the service settings',
    dependency_issue: 'A problem with a service this one relies on',
    application_error: 'An error inside the application',
    multi_layer_failure: 'Problems across several parts of the system',
    unknown: 'Cause not yet identified',
  }
  return labels[type] || type.replace(/_/g, ' ')
}

function RawDataDialog({ evidence, onClose }: { evidence: Evidence; onClose: () => void }) {
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const copyRawData = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(evidence.raw_data, null, 2))
      setCopied(true)
    } catch (error) {
      console.error('Could not copy evidence data', error)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="raw-data-title"
        className="flex max-h-[88vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-dark-200 bg-white shadow-2xl dark:border-dark-700 dark:bg-dark-900"
        onClick={event => event.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-4 border-b border-dark-200 p-5 dark:border-dark-700">
          <div className="min-w-0">
            <h2 id="raw-data-title" className="text-lg font-semibold text-dark-900 dark:text-dark-100">
              Evidence details
            </h2>
            <p className="mt-1 text-sm text-dark-500 dark:text-dark-400">{evidence.description}</p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{evidence.evidence_type.replace(/_/g, ' ')}</Badge>
              <Badge variant="outline">{evidence.source}</Badge>
              <Badge variant="outline">{formatConfidence(evidence.confidence)} confidence</Badge>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Button variant="outline" size="sm" onClick={copyRawData}>
              {copied ? <Check className="mr-2 h-4 w-4" /> : <Copy className="mr-2 h-4 w-4" />}
              {copied ? 'Copied' : 'Copy data'}
            </Button>
            <Button variant="ghost" size="sm" className="h-9 w-9 p-0" onClick={onClose} aria-label="Close evidence details">
              <X className="h-4 w-4" />
            </Button>
          </div>
        </header>
        <div className="overflow-y-auto p-5">
          <RawDataValue value={evidence.raw_data} />
        </div>
      </section>
    </div>
  )
}

function RawDataValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <span className="text-sm italic text-dark-400">No value</span>
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-sm text-dark-400">No items</span>
    return (
      <ol className="space-y-2">
        {value.map((item, index) => (
          <li key={index} className="flex gap-3 rounded-lg bg-dark-50 p-3 dark:bg-dark-800/70">
            <span className="shrink-0 font-mono text-xs text-dark-400">{index + 1}</span>
            <div className="min-w-0 flex-1"><RawDataValue value={item} /></div>
          </li>
        ))}
      </ol>
    )
  }

  if (typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0) return <span className="text-sm text-dark-400">No fields</span>
    return (
      <dl className="grid gap-3 sm:grid-cols-2">
        {entries.map(([key, child]) => (
          <div key={key} className="min-w-0 rounded-lg border border-dark-100 p-3 dark:border-dark-700">
            <dt className="mb-1 text-xs font-semibold uppercase tracking-wide text-dark-500 dark:text-dark-400">
              {key.replace(/([A-Z])/g, ' $1').replace(/[_-]/g, ' ')}
            </dt>
            <dd className="min-w-0 text-sm text-dark-800 dark:text-dark-200"><RawDataValue value={child} /></dd>
          </div>
        ))}
      </dl>
    )
  }

  if (typeof value === 'string') {
    return value.includes('\n') || value.length > 240
      ? <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md bg-dark-100 p-3 font-mono text-xs leading-relaxed dark:bg-dark-950">{value}</pre>
      : <span className="break-words">{value || '—'}</span>
  }

  return <span className="font-mono text-sm">{String(value)}</span>
}
