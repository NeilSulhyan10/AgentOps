import { Link } from 'react-router-dom'
import type { Run } from '../../types/apps'
import { Badge } from '../ui/Badge'
import { formatDate, getStatusColor, cn } from '../../utils/helpers'

export function MatchBadge({ match }: { match: boolean | null }) {
  if (match === null) return null
  return <Badge variant={match ? 'success' : 'destructive'}>{match ? 'matches ground truth' : 'does not match'}</Badge>
}

export const cause = (run: Run) => (run.root_cause_type ? run.root_cause_type.replace(/_/g, ' ') : '—')

/** One row per run, newest first. `label` adds a leading column (for example the scenario). */
export function RunsTable({ runs, label, currentId }: { runs: Run[]; label?: (run: Run) => string; currentId?: string }) {
  if (runs.length === 0) return <p className="text-sm text-dark-500 dark:text-dark-400">No runs yet.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-dark-200 dark:border-dark-700 text-left text-xs uppercase tracking-wide text-dark-500">
            <th className="py-2 pr-3">Started</th>
            {label && <th className="py-2 pr-3">Scenario</th>}
            <th className="py-2 pr-3">Status</th>
            <th className="py-2 pr-3">Root cause</th>
            <th className="py-2 pr-3">Confidence</th>
            <th className="py-2 pr-3">Took</th>
            <th className="py-2 pr-3">Agents</th>
            <th className="py-2" />
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.investigation_id} className={cn('border-b border-dark-100 dark:border-dark-800', run.investigation_id === currentId && 'bg-primary-50 dark:bg-primary-900/10')}>
              <td className="py-2 pr-3 whitespace-nowrap">{formatDate(run.created_at)}</td>
              {label && <td className="py-2 pr-3">{label(run)}</td>}
              <td className="py-2 pr-3"><Badge className={getStatusColor(run.status)}>{run.status.replace(/_/g, ' ')}</Badge></td>
              <td className="py-2 pr-3">
                <div className="flex flex-wrap items-center gap-2"><span>{cause(run)}</span><MatchBadge match={run.matches_expected} /></div>
              </td>
              <td className="py-2 pr-3 font-mono">{run.root_cause_type ? `${Math.round(run.confidence * 100)}%` : '—'}</td>
              <td className="py-2 pr-3 whitespace-nowrap">{run.duration_s != null ? `${run.duration_s}s` : '—'}</td>
              <td className="py-2 pr-3 text-dark-500">{run.agents_invoked.map((a) => a.replace('_analyzer', '')).join(', ') || '—'}</td>
              <td className="py-2 text-right">
                {run.investigation_id === currentId
                  ? <span className="text-xs text-dark-500">this run</span>
                  : <Link className="text-primary-600 hover:underline" to={`/investigation/${run.investigation_id}`}>Open</Link>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
