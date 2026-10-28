import { useState, useEffect } from 'react'
import { incidentApi } from '../api/client'
import type { InvestigationStatusResponse, InvestigationStatus } from '../types'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/Card'
import { Badge } from './ui/Badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from './ui/Table'
import { Button } from './ui/Button'
import { formatIncidentId, formatRelativeTime, truncate } from '../utils/helpers'
import { AlertTriangle, Search, Plus, Activity, CheckCircle2, Gauge, ListChecks, Eye, Bug, Trash2, Loader2, X } from 'lucide-react'
import { cn } from '../utils/helpers'
import { useNavigate } from 'react-router-dom'
import { RunIssuesDialog } from './RunIssuesDialog'

export function IncidentList() {
  const navigate = useNavigate()
  const [incidents, setIncidents] = useState<InvestigationStatusResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<InvestigationStatus | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [issuesFor, setIssuesFor] = useState<string | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<InvestigationStatusResponse | null>(null)

  const fetchIncidents = async () => {
    try {
      setLoading(true)
      const data = await incidentApi.list()
      setIncidents(data)
      setError(null)
    } catch (err) {
      setError('Failed to load incidents')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchIncidents()
  }, [])

  useEffect(() => {
    if (!deleteTarget || deletingId) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDeleteTarget(null)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [deleteTarget, deletingId])

  const deleteInvestigation = async () => {
    if (!deleteTarget) return
    const incident = deleteTarget
    const label = incident.incident_title || formatIncidentId(incident.incident_id)

    setDeletingId(incident.investigation_id)
    setActionError(null)
    try {
      await incidentApi.deleteInvestigation(incident.investigation_id)
      setIncidents(current => current.filter(item => item.investigation_id !== incident.investigation_id))
      setDeleteTarget(null)
    } catch (err) {
      console.error(err)
      setActionError(`Could not delete “${label}”. Please try again.`)
    } finally {
      setDeletingId(null)
    }
  }

  const activeCount = incidents.filter(({ status }) => status === 'pending' || status === 'running').length
  const completedCount = incidents.filter(({ status }) => status === 'completed').length
  const avgConfidence = incidents.length
    ? incidents.reduce((sum, incident) => sum + incident.overall_confidence, 0) / incidents.length
    : 0

  const filteredIncidents = incidents.filter(incident => {
    if (statusFilter !== 'all' && incident.status !== statusFilter) return false
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        incident.incident_id.toLowerCase().includes(query) ||
        (incident.service_name || '').toLowerCase().includes(query) ||
        formatIncidentId(incident.incident_id).toLowerCase().includes(query) ||
        incident.investigation_id.toLowerCase().includes(query) ||
        (incident.current_hypothesis || '').replace(/_/g, ' ').toLowerCase().includes(query)
      )
    }
    return true
  })

  const groupMap = new Map<string, InvestigationStatusResponse[]>()
  for (const incident of filteredIncidents) {
    const app = incident.service_name || 'Unknown app'
    groupMap.set(app, [...(groupMap.get(app) ?? []), incident])
  }
  const groups = [...groupMap.entries()].sort(([a], [b]) => a.localeCompare(b))

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    )
  }

  if (error) {
    return (
      <Card className="border-red-200 dark:border-red-800">
        <CardContent className="pt-6">
          <div className="flex items-center gap-3 text-red-600 dark:text-red-400">
            <AlertTriangle className="h-5 w-5" />
            <span>{error}</span>
            <Button variant="outline" size="sm" onClick={fetchIncidents}>
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <section aria-label="Incident overview" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total incidents" value={incidents.length} detail="All investigations" icon={ListChecks} tone="blue" />
        <StatCard label="Active" value={activeCount} detail="Pending or running" icon={Activity} tone="amber" />
        <StatCard label="Completed" value={completedCount} detail="Investigation finished" icon={CheckCircle2} tone="green" />
        <StatCard label="Average confidence" value={`${Math.round(avgConfidence * 100)}%`} detail="Across all investigations" icon={Gauge} tone="violet" />
      </section>

    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Incidents by app</CardTitle>
          <CardDescription>Each app's incidents are grouped in their own section</CardDescription>
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={() => navigate('/create')}>
            <Plus className="h-4 w-4 mr-2" />
            Create Incident
          </Button>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-400" />
            <input
              type="text"
              placeholder="Search incidents or apps..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-10 w-64 pl-10 pr-4 rounded-lg border border-dark-200 bg-white dark:border-dark-700 dark:bg-dark-800 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="h-10 px-4 rounded-lg border border-dark-200 bg-white dark:border-dark-700 dark:bg-dark-800 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="all">All Status</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="max_iterations_reached">Max Iterations</option>
            <option value="insufficient_evidence">Insufficient Evidence</option>
          </select>
        </div>
      </CardHeader>
    </Card>
    {filteredIncidents.length === 0 && (
      <Card><CardContent className="py-8 text-center text-dark-500">No incidents found</CardContent></Card>
    )}
    {groups.map(([app, groupIncidents]) => (
      <Card key={app} aria-label={`${app} incidents`}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {app}
            <Badge variant="secondary" className="text-xs">{groupIncidents.length}</Badge>
          </CardTitle>
          <CardDescription>
            {groupIncidents[0].namespace ? `Namespace ${groupIncidents[0].namespace} · ` : ''}incidents for this app
          </CardDescription>
        </CardHeader>
        <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Incident</TableHead>
                <TableHead>Investigation ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Iterations</TableHead>
                <TableHead>Agents</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {groupIncidents.length === 0 ? (
                <TableRow>
                  <TableCell className="text-center py-8 text-dark-500" colSpan={8}>
                    No incidents found
                  </TableCell>
                </TableRow>
              ) : (
                groupIncidents.map((incident) => (
                  <TableRow key={incident.investigation_id}>
                    <TableCell title={incident.incident_id}>
                      <button
                        type="button"
                        className="text-left font-medium text-primary-700 hover:underline dark:text-primary-300"
                        onClick={() => navigate(`/investigation/${incident.investigation_id}`)}
                      >
                        {incident.incident_title || formatIncidentId(incident.incident_id)}
                      </button>
                    </TableCell>
                    <TableCell className="font-mono text-sm">{truncate(incident.investigation_id, 12)}</TableCell>
                    <TableCell>
                      <Badge variant={incident.status === 'completed' ? 'success' : incident.status === 'running' ? 'default' : 'destructive'}>
                        {incident.status.replace('_', ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span className={cn('font-mono', getConfidenceColor(incident.overall_confidence))}>
                        {Math.round(incident.overall_confidence * 100)}%
                      </span>
                    </TableCell>
                    <TableCell>{incident.iteration_count} / 5</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {incident.agents_invoked.map((agent) => (
                          <Badge key={agent} variant="secondary" className="text-xs">
                            {agent}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-dark-500">{formatRelativeTime(incident.created_at)}</TableCell>
                    <TableCell className="whitespace-nowrap">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0"
                        aria-label={`View ${incident.incident_title || incident.incident_id}`}
                        title="View investigation"
                        onClick={() => navigate(`/investigation/${incident.investigation_id}`)}
                      >
                        <Eye className="h-4 w-4" aria-hidden="true" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0"
                        aria-label={`Show issues for ${incident.incident_title || incident.incident_id}`}
                        title="Show issues in this run"
                        onClick={() => setIssuesFor(incident.investigation_id)}
                      >
                        <Bug className="h-4 w-4" aria-hidden="true" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-8 w-8 p-0 text-red-600 hover:text-red-700 dark:text-red-400"
                        disabled={deletingId !== null}
                        aria-label={`Delete ${incident.incident_title || incident.incident_id}`}
                        title="Delete this investigation"
                        onClick={() => {
                          setActionError(null)
                          setDeleteTarget(incident)
                        }}
                      >
                        {deletingId === incident.investigation_id
                          ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                          : <Trash2 className="h-4 w-4" aria-hidden="true" />}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
        </CardContent>
      </Card>
    ))}
    {issuesFor && (
      <RunIssuesDialog
        investigationId={issuesFor}
        onClose={() => setIssuesFor(null)}
        onOpenFull={() => navigate(`/investigation/${issuesFor}`)}
      />
    )}
    {deleteTarget && (
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
        onClick={() => deletingId === null && setDeleteTarget(null)}
      >
        <section
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="delete-dialog-title"
          aria-describedby="delete-dialog-description"
          className="w-full max-w-md rounded-xl border border-dark-200 bg-white p-6 shadow-2xl dark:border-dark-700 dark:bg-dark-900"
          onClick={event => event.stopPropagation()}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <span className="rounded-full bg-red-100 p-2 text-red-700 dark:bg-red-900/40 dark:text-red-300">
                <AlertTriangle className="h-5 w-5" aria-hidden="true" />
              </span>
              <div>
                <h2 id="delete-dialog-title" className="text-lg font-semibold text-dark-900 dark:text-dark-100">Delete investigation?</h2>
                <p id="delete-dialog-description" className="mt-2 text-sm text-dark-600 dark:text-dark-300">
                  This will permanently remove <strong>{deleteTarget.incident_title || formatIncidentId(deleteTarget.incident_id)}</strong> and its investigation data.
                </p>
              </div>
            </div>
            <button
              type="button"
              className="rounded-md p-1 text-dark-500 hover:bg-dark-100 dark:hover:bg-dark-800"
              aria-label="Close delete confirmation"
              disabled={deletingId !== null}
              onClick={() => setDeleteTarget(null)}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          {actionError && <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-400">{actionError}</p>}
          <div className="mt-6 flex justify-end gap-3">
            <Button variant="outline" disabled={deletingId !== null} onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" loading={deletingId === deleteTarget.investigation_id} onClick={deleteInvestigation}>
              <Trash2 className="mr-2 h-4 w-4" aria-hidden="true" />
              Delete
            </Button>
          </div>
        </section>
      </div>
    )}
    </div>
  )
}

function StatCard({ label, value, detail, icon: Icon, tone }: {
  label: string
  value: string | number
  detail: string
  icon: typeof ListChecks
  tone: 'blue' | 'amber' | 'green' | 'violet'
}) {
  const tones = {
    blue: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
    amber: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    green: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
    violet: 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300',
  }

  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-4 pt-6">
        <div>
          <p className="text-sm font-medium text-dark-500 dark:text-dark-400">{label}</p>
          <p className="mt-1 text-3xl font-bold text-dark-900 dark:text-dark-100">{value}</p>
          <p className="mt-1 text-xs text-dark-500 dark:text-dark-400">{detail}</p>
        </div>
        <div className={`rounded-xl p-3 ${tones[tone]}`}>
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
      </CardContent>
    </Card>
  )
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.9) return 'text-green-600 dark:text-green-400'
  if (confidence >= 0.75) return 'text-blue-600 dark:text-blue-400'
  if (confidence >= 0.5) return 'text-yellow-600 dark:text-yellow-400'
  if (confidence >= 0.25) return 'text-orange-600 dark:text-orange-400'
  return 'text-red-600 dark:text-red-400'
}
