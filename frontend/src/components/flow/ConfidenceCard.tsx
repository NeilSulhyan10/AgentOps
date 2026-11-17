import type { ConfidenceBreakdown } from '../../types/flow'
import { agentLabel, cn } from '../../utils/helpers'

const pct = (n: number) => `${Math.round(n * 100)}%`
const sign = (n: number) => (n > 0 ? `+${n.toFixed(2)}` : n < 0 ? n.toFixed(2) : '0.00')

/** How the confidence number was computed, term by term (formula in backend/orchestrator/scoring.py). */
export function ConfidenceCard({ b }: { b: ConfidenceBreakdown }) {
  const rows: { label: string; value: string; hint: string; tone?: 'good' | 'bad' }[] = [
    { label: 'Base', value: b.base.toFixed(2), hint: 'best finding score among the specialists that support this root cause' },
    { label: 'Corroboration', value: sign(b.corroboration), hint: '+0.05 for each further layer that supports it (max +0.10)', tone: b.corroboration > 0 ? 'good' : undefined },
    { label: 'Contradiction', value: sign(-b.contradiction), hint: '-0.15 for each strong finding blaming a different mechanism (max -0.30)', tone: b.contradiction > 0 ? 'bad' : undefined },
    { label: 'Open questions', value: sign(-b.open_gaps), hint: '-0.05 for each question nobody has answered yet (max -0.15)', tone: b.open_gaps > 0 ? 'bad' : undefined },
    { label: 'Critic', value: `× ${b.critic.toFixed(1)}`, hint: '× 1.0 if confirmed, × 0.8 if a challenge is still open', tone: b.critic < 1 ? 'bad' : undefined },
  ]
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline gap-3">
        <span className="text-3xl font-bold text-dark-900 dark:text-dark-100">{pct(b.overall)}</span>
        <span className="text-sm text-dark-600 dark:text-dark-300">confidence in <b>{b.hypothesis.replace(/_/g, ' ')}</b> ({b.reason})</span>
      </div>

      <div className="grid gap-2 sm:grid-cols-5">
        {rows.map((r) => (
          <div key={r.label} title={r.hint} className={cn('rounded-lg border p-3', r.tone === 'bad' ? 'border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40' : r.tone === 'good' ? 'border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-950/40' : 'border-dark-200 dark:border-dark-700')}>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-dark-500">{r.label}</p>
            <p className="font-mono text-lg">{r.value}</p>
          </div>
        ))}
      </div>
      <p className="font-mono text-xs text-dark-500">overall = (base + corroboration − contradiction − open questions) × critic</p>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-dark-200 dark:border-dark-700 text-left text-xs uppercase tracking-wide text-dark-500">
              <th className="py-2 pr-3">Specialist</th><th className="pr-3">Said</th><th className="pr-3">Evidence strength</th>
              <th className="pr-3">Coverage</th><th className="pr-3">Grounding</th><th>Score</th>
            </tr>
          </thead>
          <tbody>
            {b.findings.map((f) => (
              <tr key={f.agent + f.hypothesis} className="border-b border-dark-100 dark:border-dark-800">
                <td className="py-2 pr-3">{agentLabel(f.agent)} <span className="text-dark-400">· {f.hypothesis.replace(/_/g, ' ')}</span></td>
                <td className="pr-3 font-mono">{f.reported.toFixed(2)}</td>
                <td className="pr-3 font-mono">{f.strength.toFixed(2)}</td>
                <td className="pr-3 font-mono">{f.coverage.toFixed(2)}</td>
                <td className={cn('pr-3 font-mono', f.grounding === 0 && 'text-red-600')}>{f.grounding.toFixed(2)}</td>
                <td className="font-mono font-semibold">{f.score.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="font-mono text-xs text-dark-500">score = grounding × (0.50 × said + 0.30 × strength + 0.20 × coverage)</p>
    </div>
  )
}
