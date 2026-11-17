import { useEffect, useState } from 'react'
import { ArrowRight, ArrowDown } from 'lucide-react'
import type { FlowStep, PipelineNode } from '../../types/flow'
import type { Evidence } from '../../types'
import { Badge } from '../ui/Badge'
import { boxClass, dotClass, statusWord } from './style'
import { innerFlow, mainEvent } from './innerFlow'
import { agentLabel, cn, truncate } from '../../utils/helpers'

interface Props {
  node: PipelineNode
  steps: FlowStep[]
  engine: string
  evidence: Evidence[]
  onOpenEvidence: (ev: Evidence) => void
}

/** Everything about one pipeline node: what it does, each time it ran, and what happened inside. */
export function StepDetail({ node, steps, engine, evidence, onOpenEvidence }: Props) {
  // Open on the first visit that had a problem, otherwise the last one.
  const firstProblem = steps.findIndex((s) => s.status !== 'ok')
  const [visit, setVisit] = useState(firstProblem >= 0 ? firstProblem : Math.max(steps.length - 1, 0))
  useEffect(() => setVisit(firstProblem >= 0 ? firstProblem : Math.max(steps.length - 1, 0)), [node.id, steps.length, firstProblem])

  const step = steps[visit]
  return (
    <div className="space-y-4">
      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="text-lg font-semibold font-mono text-dark-900 dark:text-dark-100">{node.id}</h3>
          <Badge variant={node.status === 'error' ? 'destructive' : node.status === 'warning' ? 'warning' : node.status === 'ok' ? 'success' : 'secondary'}>
            {statusWord[node.status]}
          </Badge>
        </div>
        <p className="mt-1 text-sm text-dark-600 dark:text-dark-300">{node.help}</p>
      </div>

      {!step ? (
        <p className="text-sm text-dark-500 dark:text-dark-400 rounded-lg border border-dashed border-dark-300 dark:border-dark-700 p-4">
          {node.visits === 0 && node.summary.startsWith('ran') ? 'This node ran but had nothing to do (nothing needed spawning).' : 'The investigation never reached this node.'}
        </p>
      ) : (
        <>
          {steps.length > 1 && (
            <div className="flex flex-wrap gap-2" role="tablist" aria-label="Visits to this node">
              {steps.map((s, i) => (
                <button
                  key={s.index}
                  role="tab"
                  aria-selected={i === visit}
                  onClick={() => setVisit(i)}
                  className={cn(
                    'flex items-center gap-2 rounded-lg border px-3 py-1.5 text-sm transition-colors',
                    i === visit ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/20' : 'border-dark-200 dark:border-dark-700 hover:bg-dark-50 dark:hover:bg-dark-800',
                  )}
                >
                  <span className={cn('h-2.5 w-2.5 rounded-full', dotClass[s.status])} />
                  Visit {i + 1}
                </button>
              ))}
            </div>
          )}

          <div>
            <p className="text-sm font-medium text-dark-900 dark:text-dark-100">
              Step {step.index}: {step.title}
              {step.duration_ms != null && <span className="ml-2 font-normal text-dark-500">{step.duration_ms} ms</span>}
            </p>
          </div>

          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-dark-500 dark:text-dark-400">Inside this step</p>
            <Stages step={step} engine={engine} />
          </div>

          {step.status !== 'ok' && (
            <div className={cn('rounded-lg border p-3 text-sm space-y-1', boxClass[step.status])}>
              <p className="font-semibold">{step.status === 'error' ? 'What went wrong' : 'Worth a look'}</p>
              {step.notes.filter(Boolean).map((n, i) => <p key={i}>{n}</p>)}
            </div>
          )}
          {step.status === 'ok' && step.notes.filter(Boolean).length > 0 && (
            <ul className="text-sm text-dark-600 dark:text-dark-300 list-disc pl-5 space-y-0.5">
              {step.notes.filter(Boolean).map((n, i) => <li key={i}>{n}</li>)}
            </ul>
          )}

          <CitedEvidence step={step} evidence={evidence} onOpenEvidence={onOpenEvidence} />

          <LlmCalls step={step} />

          <details className="text-sm">
            <summary className="cursor-pointer text-dark-500 hover:text-dark-800 dark:hover:text-dark-200">Raw flow events ({step.events.length})</summary>
            <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-dark-100 dark:bg-dark-800 p-3 text-xs">{JSON.stringify(step.events, null, 2)}</pre>
          </details>
        </>
      )}
    </div>
  )
}

function Stages({ step, engine }: { step: FlowStep; engine: string }) {
  const stages = innerFlow(step, engine)
  return (
    <div className="flex flex-col lg:flex-row lg:flex-wrap items-stretch gap-2">
      {stages.map((s, i) => (
        <div key={i} className="flex flex-col lg:flex-row items-stretch gap-2">
          <div className={cn('min-w-[130px] max-w-[260px] flex-1 rounded-lg border p-3', boxClass[s.tone])}>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-dark-500 dark:text-dark-400">{s.label}</p>
            {s.lines.map((line, j) => (
              <p key={j} className={cn('text-sm break-words', j === 0 ? 'font-medium text-dark-900 dark:text-dark-100' : 'text-dark-600 dark:text-dark-300')}>{line}</p>
            ))}
          </div>
          {i < stages.length - 1 && (
            <div className="flex items-center justify-center text-dark-400">
              <ArrowRight className="hidden lg:block h-4 w-4" />
              <ArrowDown className="lg:hidden h-4 w-4" />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

function CitedEvidence({ step, evidence, onOpenEvidence }: { step: FlowStep; evidence: Evidence[]; onOpenEvidence: (ev: Evidence) => void }) {
  const ids = (mainEvent(step)?.evidence_ids ?? []) as string[]
  if (step.node !== 'invoke_agent' || ids.length === 0) return null
  const byId = new Map(evidence.map((e) => [e.evidence_id, e]))
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-dark-500 dark:text-dark-400">Evidence this finding cites</p>
      <div className="flex flex-col gap-1.5">
        {ids.map((id) => {
          const ev = byId.get(id)
          return ev ? (
            <button
              key={id}
              onClick={() => onOpenEvidence(ev)}
              className="flex items-center gap-2 rounded-md border border-dark-200 dark:border-dark-700 px-3 py-1.5 text-left text-sm hover:bg-dark-50 dark:hover:bg-dark-800"
            >
              <Badge variant="outline">{ev.evidence_type}</Badge>
              <span className="text-dark-500">{agentLabel(ev.agent_type)}</span>
              <span className="truncate">{truncate(ev.description, 110)}</span>
            </button>
          ) : (
            <div key={id} className={cn('rounded-md border px-3 py-1.5 text-sm', boxClass.error)}>
              Evidence id <code className="font-mono">{truncate(id, 28)}</code> does not exist: the agent invented it.
            </div>
          )
        })}
      </div>
    </div>
  )
}

/** What was actually sent to the LLM and what came back (empty in rules mode). */
function LlmCalls({ step }: { step: FlowStep }) {
  const calls = step.events.filter((e) => e.event === 'llm_call')
  if (calls.length === 0) return null
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-dark-500 dark:text-dark-400">LLM call{calls.length > 1 ? 's' : ''}</p>
      <div className="space-y-2">
        {calls.map((c, i) => (
          <details key={i} className="rounded-lg border border-dark-200 dark:border-dark-700 text-sm" open={Boolean(c.error)}>
            <summary className="cursor-pointer px-3 py-2">
              {c.task}{c.agent ? ` · ${c.agent}` : ''} · {c.model || 'model'} · {c.duration_ms} ms{c.tokens ? ` · ${c.tokens} tokens` : ''}
              {c.error && <span className="ml-2 text-red-600">failed: {c.error}</span>}
            </summary>
            <div className="space-y-2 border-t border-dark-200 dark:border-dark-700 p-3">
              <p className="text-xs font-semibold text-dark-500">Sent</p>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded bg-dark-100 dark:bg-dark-800 p-2 text-xs">{c.prompt}</pre>
              <p className="text-xs font-semibold text-dark-500">Received</p>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded bg-dark-100 dark:bg-dark-800 p-2 text-xs">{c.response || '(empty)'}</pre>
            </div>
          </details>
        ))}
      </div>
    </div>
  )
}
