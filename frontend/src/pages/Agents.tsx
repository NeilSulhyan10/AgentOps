import { useEffect, useState } from 'react'
import { Loader2, Plus, Sparkles } from 'lucide-react'
import { agentApi } from '../api/client'
import type { AgentInfo, Spawnable } from '../types/flow'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { agentLabel, getAgentColor, cn } from '../utils/helpers'

const LAYERS = ['cicd', 'config', 'kubernetes', 'service', 'traffic', 'dependency']
const HYPOTHESES = ['deployment_induced_failure', 'kubernetes_oom', 'application_error', 'configuration_error', 'dependency_issue', 'traffic_incident']

const field = 'w-full rounded-md border border-dark-300 dark:border-dark-700 bg-white dark:bg-dark-900 px-3 py-2 text-sm'

export function Agents() {
  const [specialists, setSpecialists] = useState<AgentInfo[]>([])
  const [spawnable, setSpawnable] = useState<Spawnable[]>([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null)
  const [form, setForm] = useState({ name: '', description: '', layer: 'dependency', hypothesis: 'dependency_issue', evidence_types: 'log, error_rate', keywords: '' })

  const load = async () => {
    const data = await agentApi.list()
    setSpecialists(data.specialists)
    setSpawnable(data.spawnable)
    setLoading(false)
  }
  useEffect(() => { load().catch(() => setLoading(false)) }, [])

  const split = (text: string) => text.split(',').map((s) => s.trim()).filter(Boolean)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const made = await agentApi.create({ ...form, evidence_types: split(form.evidence_types), keywords: split(form.keywords) })
      setMessage({ ok: true, text: `Created ${made.name}. It is available to the next investigation.` })
      setForm({ ...form, name: '', description: '', keywords: '' })
      await load()
    } catch (err: any) {
      setMessage({ ok: false, text: err?.response?.data?.detail ?? 'Could not create the agent' })
    }
  }

  if (loading) return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-primary-500" /></div>

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-dark-900 dark:text-dark-100">Agents</h2>
        <p className="text-sm text-dark-500 dark:text-dark-400">Specialists the router can pick. Each one is a Markdown file in <code className="font-mono">backend/agents/markdown/</code>.</p>
      </div>

      <Card>
        <CardHeader><CardTitle>Available specialists ({specialists.length})</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2">
          {specialists.map((s) => (
            <div key={s.name} className="rounded-lg border border-dark-200 dark:border-dark-700 p-3">
              <div className="flex items-center gap-2">
                <Badge className={cn(getAgentColor(s.name))}>{agentLabel(s.name)}</Badge>
                <code className="text-xs text-dark-500">{s.name}</code>
                <span className="ml-auto text-xs text-dark-400">layer: {s.layer}</span>
              </div>
              <p className="mt-2 text-sm text-dark-700 dark:text-dark-200">{s.description || 'No description'}</p>
              {s.keywords.length > 0 && <p className="mt-1 text-xs text-dark-500">looks for: {s.keywords.slice(0, 8).join(', ')}</p>}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-primary-500" /> Spawned on demand</CardTitle>
          <CardDescription>
            When an incident mentions one of these and no specialist covers it, a specialist is created for that investigation only. It shows up in the Flow tab as a
            <code className="mx-1 font-mono">spawn_agent</code> step.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          {spawnable.map((s) => (
            <div key={s.name} className="rounded-lg border border-dashed border-dark-300 dark:border-dark-700 p-3">
              <p className="font-medium text-dark-900 dark:text-dark-100">{s.title}</p>
              <p className="text-sm text-dark-600 dark:text-dark-300">{s.looks_for}</p>
              <p className="mt-1 text-xs text-dark-500">triggers on: {s.keywords.slice(0, 5).join(', ')}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" /> Add a specialist</CardTitle>
          <CardDescription>Writes a new .md file with front-matter. No code change, no restart.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="grid gap-3 md:grid-cols-2">
            <label className="text-sm">Name<input className={field} required placeholder="cache_analyzer" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
            <label className="text-sm">What it looks for<input className={field} required placeholder="Redis eviction and hit ratio" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
            <label className="text-sm">Layer
              <select className={field} value={form.layer} onChange={(e) => setForm({ ...form, layer: e.target.value })}>{LAYERS.map((l) => <option key={l}>{l}</option>)}</select>
            </label>
            <label className="text-sm">Concludes
              <select className={field} value={form.hypothesis} onChange={(e) => setForm({ ...form, hypothesis: e.target.value })}>{HYPOTHESES.map((h) => <option key={h}>{h}</option>)}</select>
            </label>
            <label className="text-sm">Evidence types (comma separated)<input className={field} value={form.evidence_types} onChange={(e) => setForm({ ...form, evidence_types: e.target.value })} /></label>
            <label className="text-sm">Keywords (comma separated)<input className={field} required placeholder="redis, eviction, maxmemory" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} /></label>
            <div className="md:col-span-2 flex items-center gap-3">
              <Button type="submit">Create specialist</Button>
              {message && <span className={cn('text-sm', message.ok ? 'text-green-600' : 'text-red-600')}>{message.text}</span>}
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
