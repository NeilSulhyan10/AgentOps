import type { FlowTrace, LayerState } from '../../types/flow'
import { cn } from '../../utils/helpers'

const tile: Record<LayerState['status'], string> = {
  root: 'border-red-500 bg-red-50 dark:bg-red-950/40 border-2',
  affected: 'border-amber-400 bg-amber-50 dark:bg-amber-950/40',
  clear: 'border-green-400 bg-green-50 dark:bg-green-950/40',
  not_checked: 'border-dashed border-dark-300 dark:border-dark-700 bg-dark-50 dark:bg-dark-900',
}
const tag: Record<LayerState['status'], string> = {
  root: 'ROOT CAUSE', affected: 'affected', clear: 'checked: fine', not_checked: 'not checked',
}

/** WHERE IN YOUR APP is the fault: six layers, the root-cause layer in red. */
export function AppMap({ trace }: { trace: FlowTrace }) {
  const downstream = (key: string) => trace.layer_edges.filter((e) => e.source === key).map((e) => trace.layers.find((l) => l.key === e.target)?.name).filter(Boolean)
  const spawnedIn = (key: string) => Object.entries(trace.spawned).filter(([, s]) => s.layer === key).map(([n]) => n)
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {trace.layers.map((l) => (
        <div key={l.key} className={cn('rounded-lg border p-3', tile[l.status])}>
          <div className="flex items-center justify-between gap-2">
            <p className="font-semibold text-dark-900 dark:text-dark-100">{l.name}</p>
            <span className={cn('text-[10px] font-bold uppercase tracking-wide', l.status === 'root' ? 'text-red-600' : 'text-dark-500')}>{tag[l.status]}</span>
          </div>
          <p className="text-xs text-dark-500 dark:text-dark-400">{l.watches}</p>
          <p className="mt-1 text-sm text-dark-700 dark:text-dark-200">{l.detail}</p>
          {downstream(l.key).length > 0 && <p className="mt-1 text-[11px] text-dark-400">feeds into: {downstream(l.key).join(', ')}</p>}
          {spawnedIn(l.key).length > 0 && <p className="mt-1 text-[11px] text-primary-600">spawned here: {spawnedIn(l.key).join(', ')}</p>}
        </div>
      ))}
    </div>
  )
}
