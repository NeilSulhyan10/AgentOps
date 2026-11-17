import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Boxes } from 'lucide-react'
import { appApi } from '../api/client'
import type { AppSummary } from '../types/apps'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { cause, MatchBadge } from '../components/runs/RunsTable'
import { formatDate, getStatusColor } from '../utils/helpers'

/** One card per application AgentOps can investigate. */
export function Apps() {
  const [apps, setApps] = useState<AppSummary[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => { appApi.list().then(setApps).catch(() => setError(true)) }, [])

  if (error) return <p className="text-sm text-red-600">Could not load apps. Is the backend running?</p>
  if (!apps) return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-primary-500" /></div>

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-dark-900 dark:text-dark-100">Apps</h2>
        <p className="text-sm text-dark-500 dark:text-dark-400">Pick an application to investigate its incidents, re-run them, and compare earlier runs.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {apps.map((app) => (
          <Link key={app.key} to={`/apps/${app.key}`} className="block">
            <Card className="h-full transition-shadow hover:shadow-md">
              <CardHeader>
                <CardTitle className="flex items-center gap-2"><Boxes className="h-5 w-5 text-primary-500" />{app.name}</CardTitle>
                <CardDescription>{app.description || `Incidents for ${app.key}`}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="text-dark-600 dark:text-dark-300">{app.scenario_count} incident{app.scenario_count === 1 ? '' : 's'} · {app.run_count} run{app.run_count === 1 ? '' : 's'}</p>
                {app.last_run ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge className={getStatusColor(app.last_run.status)}>{app.last_run.status.replace(/_/g, ' ')}</Badge>
                    <span>{cause(app.last_run)}</span>
                    <MatchBadge match={null} />
                    <span className="text-xs text-dark-400">{formatDate(app.last_run.created_at)}</span>
                  </div>
                ) : <p className="text-dark-400">Not investigated yet</p>}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  )
}
