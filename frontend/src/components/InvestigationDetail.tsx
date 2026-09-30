import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { investigationApi } from '../api/client'
import type { InvestigationState, TimelineEntry, AgentType } from '../types'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/Card'
import { Badge } from './ui/Badge'
import { Tabs, TabsList, TabsTrigger, TabsContent } from './ui/Tabs'
import { Progress } from './ui/Progress'
import { Button } from './ui/Button'
import { formatDate, getStatusColor, getAgentColor, formatConfidence, getConfidenceColor, truncate } from '../utils/helpers'
import { 
  AlertTriangle, 
  Brain, 
  ArrowRight,
  ChevronRight,
  FileText,
  Wrench,
  Zap,
  BarChart2
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
  const [investigation, setInvestigation] = useState<InvestigationState | null>(null)
  const [timeline, setTimeline] = useState<TimelineEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    )
  }

  if (error || !investigation) {
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-dark-900 dark:text-dark-100">
            Investigation {truncate(investigation.investigation_id, 12)}
          </h1>
          <p className="text-dark-500 dark:text-dark-400">Incident: {truncate(investigation.incident_id, 12)}</p>
        </div>
        <div className="flex items-center gap-3">
          <Badge className={cn('text-sm', getStatusColor(investigation.investigation_status))}>
            {investigation.investigation_status.replace('_', ' ')}
          </Badge>
          <Button variant="ghost" onClick={() => navigate('/')}>
            Back to List
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Overall Confidence</CardTitle>
            <CardDescription>Combined confidence from all agents</CardDescription>
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
                    strokeDashoffset={364.4 - (364.4 * investigation.overall_confidence)}
                    strokeLinecap="round"
                    fill="none"
                    className={cn('transition-all duration-1000', getConfidenceColor(investigation.overall_confidence))}
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className={cn('text-3xl font-bold', getConfidenceColor(investigation.overall_confidence))}>
                    {formatConfidence(investigation.overall_confidence)}
                  </span>
                </div>
              </div>
              <Progress value={investigation.overall_confidence * 100} className="w-full max-w-xs mx-auto" />
              <p className="mt-2 text-sm text-dark-500">
                Threshold: {Math.round(0.75 * 100)}% • {investigation.investigation_status === 'completed' ? 'Threshold met' : 'Below threshold'}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Agents Invoked</CardTitle>
            <CardDescription>{investigation.agents_invoked.length} of 3 agents</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {['cicd', 'kubernetes', 'observability'].map((agent) => {
                const invoked = investigation.agents_invoked.includes(agent as AgentType)
                const confidence = investigation.confidence_scores[agent as AgentType]
                return (
                  <div
                    key={agent}
                    className={cn(
                      'flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors',
                      invoked
                        ? getAgentColor(agent).replace('bg-', 'bg-').replace('text-', 'text-')
                        : 'bg-dark-100 text-dark-400 dark:bg-dark-800 dark:text-dark-500'
                    )}
                  >
                    <span className={cn(getAgentColor(agent).replace('bg-', 'text-').replace('text-', 'text-'))}>
                      {agentLabels[agent as AgentType]}
                    </span>
                    {invoked && confidence && (
                      <span className={cn('font-mono text-xs', getConfidenceColor(confidence))}>
                        {formatConfidence(confidence)}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Current Hypothesis</CardTitle>
            <CardDescription>Primary investigation direction</CardDescription>
          </CardHeader>
          <CardContent>
            {investigation.current_hypothesis ? (
              <Badge variant="default" className="text-base px-3 py-1">
                {investigation.current_hypothesis.replace(/_/g, ' ')}
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
                    <p className="font-mono text-sm">{investigation.investigation_id}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-500 dark:text-dark-400">Incident ID</p>
                    <p className="font-mono text-sm">{investigation.incident_id}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-500 dark:text-dark-400">Started</p>
                    <p className="font-mono text-sm">{formatDate(investigation.created_at)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-500 dark:text-dark-400">Completed</p>
                    <p className="font-mono text-sm">{investigation.completed_at ? formatDate(investigation.completed_at) : 'In progress'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-500 dark:text-dark-400">Iterations</p>
                    <p className="font-mono text-sm">{investigation.iteration_count} / {investigation.max_iterations}</p>
                  </div>
                  <div>
                    <p className="text-sm text-dark-500 dark:text-dark-400">Evidence Collected</p>
                    <p className="font-mono text-sm">{investigation.evidence.length}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Agent Findings</CardTitle>
              </CardHeader>
              <CardContent>
                {investigation.agent_findings.length === 0 ? (
                  <p className="text-dark-500 dark:text-dark-400 text-center py-8">No agent findings yet</p>
                ) : (
                  <div className="space-y-4">
                    {investigation.agent_findings.map((finding) => (
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
          <ConfidenceChart confidenceHistory={investigation.confidence_history} />
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
              {investigation.evidence.length === 0 ? (
                <p className="text-dark-500 dark:text-dark-400 text-center py-8">No evidence collected yet</p>
              ) : (
                <div className="space-y-3">
                  {investigation.evidence.map((ev) => (
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
                          <Button variant="ghost" size="sm" onClick={() => alert(JSON.stringify(ev.raw_data, null, 2))}>
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
          {investigation.root_cause ? (
            <div className="space-y-6">
              <Card className="border-l-4 border-red-500">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-red-500" />
                    Root Cause Analysis
                  </CardTitle>
                  <CardDescription>Final root cause determination with confidence</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                    <p className="text-dark-900 dark:text-dark-100">{investigation.root_cause.root_cause}</p>
                  </div>
                  <div className="grid gap-4 md:grid-cols-3">
                    <div>
                      <p className="text-sm text-dark-500 dark:text-dark-400">Root Cause Type</p>
                      <p className="font-medium">{investigation.root_cause.root_cause_type.replace(/_/g, ' ')}</p>
                    </div>
                    <div>
                      <p className="text-sm text-dark-500 dark:text-dark-400">Overall Confidence</p>
                      <p className={cn('font-mono text-lg font-bold', getConfidenceColor(investigation.root_cause.overall_confidence))}>
                        {formatConfidence(investigation.root_cause.overall_confidence)}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-dark-500 dark:text-dark-400">Agents Consulted</p>
                      <p className="font-medium">{investigation.root_cause.agents_consulted.length}</p>
                    </div>
                  </div>
                  {investigation.root_cause.contributing_factors.length > 0 && (
                    <div>
                      <h4 className="font-medium mb-2">Contributing Factors</h4>
                      <ul className="space-y-1">
                        {investigation.root_cause.contributing_factors.map((factor, i) => (
                          <li key={i} className="flex items-center gap-2 text-sm text-dark-600 dark:text-dark-300">
                            <ChevronRight className="h-4 w-4 text-dark-400" />
                            {factor}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {investigation.root_cause.evidence.length > 0 && (
                    <div>
                      <h4 className="font-medium mb-2">Supporting Evidence</h4>
                      <div className="flex flex-wrap gap-2">
                        {investigation.root_cause.evidence.map((ev, i) => (
                          <Badge key={i} variant="outline" className="text-xs">
                            {truncate(ev, 50)}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {investigation.remediation && (
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
                      <p className="text-dark-900 dark:text-dark-100">{investigation.remediation.recommendation}</p>
                    </div>
                    <div>
                      <h4 className="font-medium mb-2">Remediation Steps</h4>
                      <ol className="space-y-2">
                        {investigation.remediation.steps.map((step, i) => (
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
                        <Badge variant={investigation.remediation.priority === 'high' ? 'destructive' : 'default'}>
                          {investigation.remediation.priority}
                        </Badge>
                      </div>
                      <div>
                        <p className="text-sm text-dark-500 dark:text-dark-400">Effort</p>
                        <Badge variant="secondary">{investigation.remediation.estimated_effort}</Badge>
                      </div>
                      <div>
                        <p className="text-sm text-dark-500 dark:text-dark-400">Risk Level</p>
                        <Badge variant={investigation.remediation.risk_level === 'high' ? 'destructive' : 'secondary'}>
                          {investigation.remediation.risk_level}
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
    </div>
  )
}