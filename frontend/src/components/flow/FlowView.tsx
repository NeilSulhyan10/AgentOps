import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, XCircle, Loader2, MousePointerClick } from 'lucide-react'
import { flowApi } from '../../api/client'
import type { ConfidenceBreakdown, FlowTrace } from '../../types/flow'
import type { Evidence } from '../../types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { PipelineDiagram } from './PipelineDiagram'
import { StepDetail } from './StepDetail'
import { AppMap } from './AppMap'
import { ConfidenceCard } from './ConfidenceCard'
import { boxClass, dotClass } from './style'
import { agentLabel, cn } from '../../utils/helpers'

interface Props {
  investigationId: string
  running: boolean
  refreshKey: number                       // changes whenever a live event arrives
  evidence: Evidence[]
  onOpenEvidence: (ev: Evidence) => void
}

/** The Flow tab: where did the investigation go, and where did it go wrong? */
export function FlowView({ investigationId, running, refreshKey, evidence, onOpenEvidence }: Props) {
  const [trace, setTrace] = useState<FlowTrace | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const data = await flowApi.get(investigationId)
        if (!cancelled) { setTrace(data); setError(null) }
      } catch {
        if (!cancelled) setError('No flow data yet. The flow log (logs/flow.jsonl) has no events for this investigation.')
      }
    }
    load()
    const timer = running ? setInterval(load, 2500) : undefined
    return () => { cancelled = true; if (timer) clearInterval(timer) }
  }, [investigationId, running, refreshKey])

  // First time the trace arrives, open the first node that went wrong (or the last one that ran).
  useEffect(() => {
    if (!trace || selected) return
    const bad = trace.steps.find((s) => s.status !== 'ok')
    setSelected(bad ? bad.node : trace.steps[trace.steps.length - 1]?.node ?? null)
  }, [trace, selected])

  const node = useMemo(() => trace?.pipeline.nodes.find((n) => n.id === selected) ?? null, [trace, selected])

  if (error && !trace) {
    return <Card><CardContent className="pt-6 text-sm text-dark-500">{error}</CardContent></Card>
  }
  if (!trace) {
    return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-primary-500" /></div>
  }

  const problems = trace.steps.filter((s) => s.status !== 'ok')
  const tone = trace.worst_status === 'error' ? 'error' : trace.worst_status === 'warning' ? 'warning' : 'ok'
  const Icon = tone === 'error' ? XCircle : tone === 'warning' ? AlertTriangle : CheckCircle2

  return (
    <div className="space-y-6">
      {/* 1. The answer first: how did this run end, and is anything wrong? */}
      <div className={cn('flex items-start gap-3 rounded-xl border p-4', boxClass[tone])}>
        <Icon className={cn('h-6 w-6 mt-0.5 shrink-0', tone === 'error' ? 'text-red-600' : tone === 'warning' ? 'text-amber-600' : 'text-green-600')} />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-dark-900 dark:text-dark-100">{trace.headline}</p>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-dark-600 dark:text-dark-300">
            <Badge variant="secondary">decisions by: {trace.engine || 'unknown'}</Badge>
            {trace.fault && <Badge variant="destructive">injected fault: {trace.fault}</Badge>}
            {Object.keys(trace.spawned).length > 0 && <Badge variant="default">spawned: {Object.keys(trace.spawned).map(agentLabel).join(', ')}</Badge>}
          </div>
          {problems.length > 0 && (
            <ul className="mt-3 space-y-1">
              {problems.map((s) => (
                <li key={s.index}>
                  <button className="text-left text-sm underline decoration-dotted underline-offset-2 hover:text-primary-700" onClick={() => setSelected(s.node)}>
                    Step {s.index} · {s.node}: {s.notes.find(Boolean) ?? s.title}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* 2. The pipeline, and what is inside whichever node you click. */}
      <Card>
        <CardHeader>
          <CardTitle>How AgentOps investigated</CardTitle>
          <CardDescription className="flex items-center gap-1">
            <MousePointerClick className="h-4 w-4" /> Click any box to look inside it. The thick blue line is the path taken; green is fine, amber is worth a look, red failed, dashed grey was never reached.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,560px)_minmax(0,1fr)]">
            <PipelineDiagram nodes={trace.pipeline.nodes} edges={trace.pipeline.edges} selected={selected} onSelect={setSelected} />
            <div className="rounded-xl border border-dark-200 dark:border-dark-700 p-4 min-w-0">
              {node ? (
                <StepDetail
                  node={node}
                  steps={trace.steps.filter((s) => s.node === node.id)}
                  engine={trace.engine}
                  evidence={evidence}
                  onOpenEvidence={onOpenEvidence}
                />
              ) : <p className="text-sm text-dark-500">Select a box on the left.</p>}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 3. The same investigation seen from the application's side. */}
      <Card>
        <CardHeader>
          <CardTitle>Where in the application</CardTitle>
          <CardDescription>The layers of the investigated service. Red holds the root cause; amber layers show symptoms or contributing factors.</CardDescription>
        </CardHeader>
        <CardContent><AppMap trace={trace} /></CardContent>
      </Card>

      {/* 4. Where the confidence number comes from. */}
      {'overall' in trace.confidence_breakdown && (
        <Card>
          <CardHeader>
            <CardTitle>How confident, and why</CardTitle>
            <CardDescription>The number is computed from the evidence, not just taken from what the agents claim. Hover a term for its rule.</CardDescription>
          </CardHeader>
          <CardContent><ConfidenceCard b={trace.confidence_breakdown as ConfidenceBreakdown} /></CardContent>
        </Card>
      )}

      {/* 5. What each specialist concluded. */}
      <Card>
        <CardHeader>
          <CardTitle>What each specialist found</CardTitle>
          <CardDescription>Findings that cite evidence which does not exist are ignored when confidence is computed.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="divide-y divide-dark-100 dark:divide-dark-800">
            {Object.entries(trace.findings).map(([agent, f]) => (
              <div key={agent} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                <span className={cn('h-2.5 w-2.5 rounded-full', f.grounded ? dotClass.ok : dotClass.warning)} title={f.grounded ? 'cites real evidence' : 'ignored: cites no real evidence'} />
                <span className="w-32 font-medium text-dark-900 dark:text-dark-100">{agentLabel(agent)}</span>
                {agent in trace.spawned && <Badge variant="default">spawned</Badge>}
                <span className="flex-1 text-dark-600 dark:text-dark-300">{f.hypothesis.replace(/_/g, ' ')}</span>
                <div className="h-2 w-28 rounded-full bg-dark-100 dark:bg-dark-800 overflow-hidden"><div className="h-full bg-primary-500" style={{ width: `${Math.round(f.confidence * 100)}%` }} /></div>
                <span className="w-10 text-right font-mono text-xs">{Math.round(f.confidence * 100)}%</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
