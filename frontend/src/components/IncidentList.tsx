import { useState, useEffect } from 'react'
import { incidentApi } from '../api/client'
import type { InvestigationStatusResponse, InvestigationStatus } from '../types'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/Card'
import { Badge } from './ui/Badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from './ui/Table'
import { Button } from './ui/Button'
import { formatRelativeTime, truncate } from '../utils/helpers'
import { AlertTriangle, Search, Plus } from 'lucide-react'
import { cn } from '../utils/helpers'
import { useNavigate } from 'react-router-dom'

export function IncidentList() {
  const navigate = useNavigate()
  const [incidents, setIncidents] = useState<InvestigationStatusResponse[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<InvestigationStatus | 'all'>('all')
  const [searchQuery, setSearchQuery] = useState('')

  const fetchIncidents = async () => {
    try {
      setLoading(true)
      const status = statusFilter === 'all' ? undefined : statusFilter
      const data = await incidentApi.list(status)
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
  }, [statusFilter])

  const filteredIncidents = incidents.filter(incident => {
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        incident.incident_id.toLowerCase().includes(query) ||
        incident.incident_id.toLowerCase().includes(query)
      )
    }
    return true
  })

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
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Incidents</CardTitle>
          <CardDescription>All reported incidents and their investigation status</CardDescription>
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
              placeholder="Search incidents..."
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
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Incident ID</TableHead>
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
              {filteredIncidents.length === 0 ? (
                <TableRow>
                  <TableCell className="text-center py-8 text-dark-500" colSpan={8}>
                    No incidents found
                  </TableCell>
                </TableRow>
              ) : (
                filteredIncidents.map((incident) => (
                  <TableRow key={incident.investigation_id}>
                    <TableCell className="font-mono text-sm">{truncate(incident.incident_id, 12)}</TableCell>
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
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => window.location.href = `/investigation/${incident.investigation_id}`}
                      >
                        View
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
  )
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.9) return 'text-green-600 dark:text-green-400'
  if (confidence >= 0.75) return 'text-blue-600 dark:text-blue-400'
  if (confidence >= 0.5) return 'text-yellow-600 dark:text-yellow-400'
  if (confidence >= 0.25) return 'text-orange-600 dark:text-orange-400'
  return 'text-red-600 dark:text-red-400'
}