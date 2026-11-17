import type { FlowStatus } from '../../types/flow'

// Literal class strings so Tailwind sees them. Same meaning everywhere:
// green = fine, amber = worth a look, red = the fault, grey = not reached.
export const nodeClass: Record<FlowStatus, string> = {
  ok: 'fill-green-50 stroke-green-600 dark:fill-green-950 dark:stroke-green-500',
  warning: 'fill-amber-50 stroke-amber-600 dark:fill-amber-950 dark:stroke-amber-500',
  error: 'fill-red-50 stroke-red-600 dark:fill-red-950 dark:stroke-red-500',
  skipped: 'fill-dark-50 stroke-dark-300 dark:fill-dark-900 dark:stroke-dark-700',
}

export const dotClass: Record<FlowStatus, string> = {
  ok: 'bg-green-500',
  warning: 'bg-amber-500',
  error: 'bg-red-500',
  skipped: 'bg-dark-300 dark:bg-dark-600',
}

export const boxClass: Record<FlowStatus, string> = {
  ok: 'border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-950/40',
  warning: 'border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/40',
  error: 'border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/40',
  skipped: 'border-dark-200 bg-dark-50 dark:border-dark-700 dark:bg-dark-900',
}

export const statusWord: Record<FlowStatus, string> = {
  ok: 'OK',
  warning: 'Needs a look',
  error: 'Failed',
  skipped: 'Not reached',
}
