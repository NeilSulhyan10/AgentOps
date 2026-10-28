import { useEffect, useState } from 'react'
import { investigationApi } from '../api/client'
import type { InvestigationState } from '../types'
import { Badge } from './ui/Badge'
import { Button } from './ui/Button'
import { AlertTriangle, X, Loader2, ExternalLink } from 'lucide-react'
import { formatDate, formatIncidentId } from '../utils/helpers'

interface Props {
  investigationId: string
  onClose: () => void
  onOpenFull: () => void
}

export function RunIssuesDialog({ investigationId, onClose, onOpenFull }: Props) {
  const [inv, setInv] = useState<InvestigationState | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    investigationApi.get(investigationId)
      .then(data => { if (!cancelled) setInv(data) })
      .catch(() => { if (!cancelled) setError('Could not load issues for this run.') })
    return () => { cancelled = true }
  }, [investigationId])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const incident = inv?.incident
  const meta = incident?.metadata ?? {}
  const runId = meta.github_workflow_run_id
  const runNumber = meta.github_workflow_run_number

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="run-issues-title"
        className="max-h-[85vh] w-full max-w-3xl overflow-y-auto rounded-xl border border-dark-200 bg-white p-6 shadow-2xl dark:border-dark-700 dark:bg-dark-900"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="run-issues-title" className="text-lg font-semibold text-dark-900 dark:text-dark-100">
              Issues in this run
            </h2>
            {incident && (
              <p className="mt-1 text-sm text-dark-600 dark:text-dark-300">
                {incident.title || formatIncidentId(incident.incident_id)}
              </p>
            )}
          </div>
          <button type="button" aria-label="Close" onClick={onClose}
            className="rounded-md p-1 text-dark-500 hover:bg-dark-100 dark:hover:bg-dark-800">
            <X className="h-4 w-4" />
          </button>
        </div>

        {!inv && !error && (
          <div className="flex justify-center py-10"><Loader2 className="h-6 w-6 animate-spin" /></div>
        )}
        {error && <p role="alert" className="mt-4 text-sm text-red-600 dark:text-red-400">{error}</p>}

        {inv && incident && (
          <div className="mt-4 space-y-5">
            <dl className="grid grid-cols-2 gap-3 rounded-lg bg-dark-50 p-3 text-sm dark:bg-dark-800">
              <Field label="App / service" value={incident.service_name} />
              <Field label="Namespace" value={incident.namespace} />
              <Field label="Run instance" value={inv.investigation_id} mono />
              <Field label="Incident" value={incident.incident_id} mono />
              {runId && <Field label="CI run" value={`#${runNumber ?? ''} (id ${runId})`} />}
              <Field label="Started" value={formatDate(inv.created_at)} />
              <Field label="Severity" value={incident.severity} />
              <Field label="Status" value={inv.investigation_status.replace(/_/g, ' ')} />
            </dl>

            <Group title={`Root cause${inv.root_cause ? '' : ' (not determined yet)'}`}>
              {inv.root_cause && (
                <>
                  <p className="text-sm">{inv.root_cause.root_cause}</p>
                  {inv.root_cause.contributing_factors.length > 0 && (
                    <ul className="mt-2 list-disc pl-5 text-sm text-dark-600 dark:text-dark-300">
                      {inv.root_cause.contributing_factors.map((f, i) => <li key={i}>{f}</li>)}
                    </ul>
                  )}
                </>
              )}
            </Group>

            <Group title={`Findings (${inv.agent_findings.length})`}>
              {inv.agent_findings.length === 0 && <Empty text="No findings recorded." />}
              {inv.agent_findings.map(f => (
                <div key={f.finding_id} className="rounded-lg border border-dark-200 p-3 dark:border-dark-700">
                  <div className="mb-1 flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">{f.agent_type}</Badge>
                    <span className="text-xs text-dark-500">iteration {f.iteration} · {Math.round(f.confidence * 100)}%</span>
                  </div>
                  <p className="text-sm">{f.finding}</p>
                </div>
              ))}
            </Group>

            <Group title={`Open evidence gaps (${inv.evidence_gaps.length})`}>
              {inv.evidence_gaps.length === 0 && <Empty text="None." />}
              {inv.evidence_gaps.map((g, i) => (
                <div key={i} className="flex items-start gap-2 text-sm">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden="true" />{g}
                </div>
              ))}
            </Group>

            <Group title={`Evidence (${inv.evidence.length})`}>
              {inv.evidence.length === 0 && <Empty text="No evidence collected." />}
              {inv.evidence.map(e => (
                <div key={e.evidence_id} className="text-sm">
                  <Badge variant="secondary" className="mr-2 text-xs">{e.agent_type}</Badge>{e.description}
                </div>
              ))}
            </Group>
          </div>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <Button variant="outline" onClick={onClose}>Close</Button>
          <Button onClick={onOpenFull}>
            <ExternalLink className="mr-2 h-4 w-4" aria-hidden="true" />Full investigation
          </Button>
        </div>
      </section>
    </div>
  )
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-dark-500">{label}</dt>
      <dd className={`truncate ${mono ? 'font-mono text-xs' : ''}`} title={value}>{value}</dd>
    </div>
  )
}

function Group({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold text-dark-900 dark:text-dark-100">{title}</h3>
      <div className="space-y-2">{children}</div>
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <p className="text-sm text-dark-500">{text}</p>
}
