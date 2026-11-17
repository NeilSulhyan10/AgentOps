import type { PipelineEdge, PipelineNode } from '../../types/flow'
import { nodeClass } from './style'
import { cn } from '../../utils/helpers'

const NODE_W = 230
const NODE_H = 58
const GAP = 34
const CX = 190          // centre line of the nodes
const WIDTH = 560

interface Props {
  nodes: PipelineNode[]
  edges: PipelineEdge[]
  selected: string | null
  onSelect: (id: string) => void
}

/** The investigation graph, top to bottom. Click a node to look inside it. The thick blue line is the path actually taken. */
export function PipelineDiagram({ nodes, edges, selected, onSelect }: Props) {
  const index = new Map(nodes.map((n, i) => [n.id, i]))
  const top = (i: number) => 16 + i * (NODE_H + GAP)
  const height = top(nodes.length) - GAP + 16

  const edgePath = (e: PipelineEdge) => {
    const a = index.get(e.source)
    const b = index.get(e.target)
    if (a === undefined || b === undefined) return null
    if (b === a + 1) {                                  // straight down
      return { d: `M ${CX} ${top(a) + NODE_H} L ${CX} ${top(b) - 2}` }
    }
    const span = Math.abs(b - a)
    if (b > a) {                                        // skips ahead: curve on the left
      const x = CX - NODE_W / 2
      const off = 40 + span * 4
      return { d: `M ${x} ${top(a) + NODE_H / 2} C ${x - off} ${top(a) + NODE_H / 2}, ${x - off} ${top(b) + NODE_H / 2}, ${x - 2} ${top(b) + NODE_H / 2}` }
    }
    const x = CX + NODE_W / 2                           // loops back: curve on the right
    const off = 36 + span * 14
    return { d: `M ${x} ${top(a) + NODE_H / 2} C ${x + off} ${top(a) + NODE_H / 2}, ${x + off} ${top(b) + NODE_H / 2}, ${x + 2} ${top(b) + NODE_H / 2}` }
  }

  return (
    <svg viewBox={`0 0 ${WIDTH} ${height}`} className="w-full max-w-[560px] mx-auto" role="img" aria-label="Investigation pipeline">
      <defs>
        <marker id="arrow-taken" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="10" markerHeight="10" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" className="fill-primary-600" />
        </marker>
        <marker id="arrow-idle" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" className="fill-dark-300 dark:fill-dark-600" />
        </marker>
      </defs>

      {[...edges].sort((a, b) => Number(a.taken) - Number(b.taken)).map((e) => {
        const p = edgePath(e)
        if (!p) return null
        return (
          <path
            key={`${e.source}-${e.target}`}
            d={p.d}
            fill="none"
            strokeWidth={e.taken ? 3 : 1.5}
            strokeDasharray={e.taken ? undefined : '4 4'}
            markerEnd={e.taken ? 'url(#arrow-taken)' : 'url(#arrow-idle)'}
            className={e.taken ? 'stroke-primary-600' : 'stroke-dark-300 dark:stroke-dark-600'}
          />
        )
      })}

      {nodes.map((n, i) => {
        const x = CX - NODE_W / 2
        const y = top(i)
        const isSelected = selected === n.id
        return (
          <g
            key={n.id}
            role="button"
            tabIndex={0}
            aria-label={`${n.id}: ${n.summary}`}
            onClick={() => onSelect(n.id)}
            onKeyDown={(ev) => (ev.key === 'Enter' || ev.key === ' ') && onSelect(n.id)}
            className="cursor-pointer outline-none group"
          >
            <rect
              x={x} y={y} width={NODE_W} height={NODE_H} rx={10}
              strokeWidth={isSelected ? 4 : n.status === 'error' ? 3 : 2}
              strokeDasharray={n.status === 'skipped' ? '5 4' : undefined}
              className={cn(nodeClass[n.status], 'transition-all group-hover:brightness-95 group-focus-visible:stroke-primary-500')}
            />
            <text x={CX} y={y + 24} textAnchor="middle" className="fill-dark-900 dark:fill-dark-100 text-[14px] font-semibold font-mono pointer-events-none">
              {n.id}
            </text>
            <text x={CX} y={y + 42} textAnchor="middle" className="fill-dark-500 dark:fill-dark-400 text-[11px] pointer-events-none">
              {n.summary.length > 38 ? n.summary.slice(0, 37) + '…' : n.summary}
            </text>
            {n.visits > 1 && (
              <g className="pointer-events-none">
                <circle cx={x + NODE_W - 4} cy={y + 4} r={11} className="fill-primary-600" />
                <text x={x + NODE_W - 4} y={y + 8} textAnchor="middle" className="fill-white text-[11px] font-bold">{n.visits}×</text>
              </g>
            )}
            {n.status === 'error' && <text x={x + 12} y={y + 24} className="fill-red-600 text-[16px] font-bold pointer-events-none">!</text>}
            {n.status === 'warning' && <text x={x + 12} y={y + 24} className="fill-amber-600 text-[16px] font-bold pointer-events-none">!</text>}
          </g>
        )
      })}
    </svg>
  )
}
