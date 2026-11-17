import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Loader2, Play, RotateCcw } from 'lucide-react'
import { appApi } from '../api/client'
import type { AppPage as AppData, AppScenario } from '../types/apps'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs'
import { cause, MatchBadge, RunsTable } from '../components/runs/RunsTable'
import { getStatusColor } from '../utils/helpers'

const active = (status: string) => status === 'running' || status === 'pending'

/** One application: its incidents with a (re-)investigate button each, and the history of every run. */
export function AppPage() {
  const { appKey = '' } = useParams()
  const navigate = useNavigate()
  const [app, setApp] = useState<AppData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [starting, setStarting] = useState<string | null>(null)
  const [filter, setFilter] = useState('')

  const load = useCallback(() => appApi.get(appKey).then((a) => { setApp(a); setError(null) }).catch(() => setError('Could not load this app.')), [appKey])
  useEffect(() => { load() }, [load])

  // Refresh while anything is still running.
  const anyActive = useMemo(() => !!app?.scenarios.some((s) => s.runs.some((r) => active(r.status))), [app])
  useEffect(() => {
    if (!anyActive) return
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [anyActive, load])

  const investigate = async (scenario: AppScenario, open: boolean) => {
    setStarting(scenario.scenario_id)
    try {
      const started = await appApi.investigate(scenario.scenario_id)
      if (open) navigate(`/investigation/${started.investigation_id}`)
      else await load()
    } catch { setError(`Could not start ${scenario.scenario_id}.`) }
    finally { setStarting(null) }
  }

  const runAll = async () => {
    if (!app) return
    for (const s of app.scenarios) await investigate(s, false)
  }

  if (error && !app) return <p className="text-sm text-red-600">{error}</p>
  if (!app) return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-primary-500" /></div>

  const allRuns = app.scenarios.flatMap((s) => s.runs).sort((a, b) => b.created_at.localeCompare(a.created_at))
  const shownRuns = filter ? allRuns.filter((r) => r.incident_id === filter) : allRuns

  return (
    <div className="space-y-6">
      <div>
        <Link to="/apps" className="inline-flex items-center gap-1 text-sm text-dark-500 hover:text-primary-600"><ArrowLeft className="h-4 w-4" />All apps</Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold text-dark-900 dark:text-dark-100">{app.name}</h2>
            <p className="text-sm text-dark-500 dark:text-dark-400">{app.description}</p>
          </div>
          <Button onClick={runAll} disabled={starting !== null}><Play className="mr-2 h-4 w-4" />Investigate all {app.scenarios.length}</Button>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      <Tabs defaultValue="incidents">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="incidents">Incidents</TabsTrigger>
          <TabsTrigger value="history">History ({allRuns.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="incidents">
          <div className="space-y-3">
            {app.scenarios.map((s) => {
              const latest = s.runs[0]
              return (
                <Card key={s.scenario_id}>
                  <CardContent className="flex flex-wrap items-center gap-4 pt-6">
                    <div className="min-w-[240px] flex-1">
                      <div className="flex items-center gap-2">
                        <code className="text-xs text-dark-500">{s.scenario_id}</code>
                        <Badge variant="outline">{s.severity}</Badge>
                      </div>
                      <p className="font-medium text-dark-900 dark:text-dark-100">{s.title}</p>
                      {s.expected_root_cause && <p className="text-xs text-dark-500">expected: {s.expected_root_cause.replace(/_/g, ' ')}</p>}
                    </div>
                    <div className="min-w-[220px] text-sm">
                      {latest ? (
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge className={getStatusColor(latest.status)}>{latest.status.replace(/_/g, ' ')}</Badge>
                            <span>{cause(latest)}</span>
                          </div>
                          <div className="flex items-center gap-2 text-xs text-dark-500">
                            <MatchBadge match={latest.matches_expected} />
                            <span>{s.runs.length} run{s.runs.length === 1 ? '' : 's'}</span>
                            <Link className="text-primary-600 hover:underline" to={`/investigation/${latest.investigation_id}`}>Open latest</Link>
                          </div>
                        </div>
                      ) : <span className="text-dark-400">Not investigated yet</span>}
                    </div>
                    <Button variant={latest ? 'outline' : 'primary'} disabled={starting !== null || (latest && active(latest.status))} onClick={() => investigate(s, true)}>
                      {starting === s.scenario_id ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : latest ? <RotateCcw className="mr-2 h-4 w-4" /> : <Play className="mr-2 h-4 w-4" />}
                      {latest ? 'Re-investigate' : 'Investigate'}
                    </Button>
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </TabsContent>

        <TabsContent value="history">
          <Card>
            <CardHeader>
              <CardTitle>Every run</CardTitle>
              <CardDescription>Re-investigating never overwrites anything: each run is kept, newest first.</CardDescription>
              <select className="mt-2 w-full max-w-sm rounded-md border border-dark-300 bg-white px-3 py-2 text-sm dark:border-dark-700 dark:bg-dark-900" value={filter} onChange={(e) => setFilter(e.target.value)}>
                <option value="">All incidents</option>
                {app.scenarios.map((s) => <option key={s.scenario_id} value={s.scenario_id}>{s.scenario_id}: {s.title}</option>)}
              </select>
            </CardHeader>
            <CardContent><RunsTable runs={shownRuns} label={(r) => r.incident_id} /></CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
