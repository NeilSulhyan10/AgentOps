import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { formatDistanceToNow, format } from 'date-fns'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(dateString: string): string {
  try {
    return format(new Date(dateString), 'MMM d, yyyy HH:mm:ss')
  } catch {
    return dateString
  }
}

export function formatRelativeTime(dateString: string): string {
  try {
    return formatDistanceToNow(new Date(dateString), { addSuffix: true })
  } catch {
    return dateString
  }
}

export function formatIncidentId(incidentId: string): string {
  const githubRunMatch = incidentId.match(/^github-actions-(.+)$/i)
  if (githubRunMatch) return `GitHub Actions #${githubRunMatch[1]}`
  return incidentId
}

export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
    case 'high':
      return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400'
    case 'medium':
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
    case 'low':
      return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
    case 'config':
      return 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
    case 'dependency':
      return 'bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-400'
    case 'traffic':
      return 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400'
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400'
  }
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
      return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
    case 'running':
    case 'investigating':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
    case 'pending':
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400'
    case 'interrupted':
      return 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
    case 'failed':
    case 'max_iterations_reached':
    case 'insufficient_evidence':
      return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400'
  }
}

const KNOWN_AGENTS: Record<string, string> = {
  cicd: 'CI/CD',
  kubernetes: 'Kubernetes',
  observability: 'Observability',
  config: 'Configuration',
  dependency: 'Dependencies',
  traffic: 'Traffic',
}

/** 'cicd_analyzer' -> 'CI/CD', 'cache_analyzer' -> 'Cache' (any agent name, including ones spawned at run time). */
export function agentLabel(agent: string | undefined | null): string {
  const key = (agent || '').replace(/_analyzer$/, '')
  if (!key) return 'Unknown'
  return KNOWN_AGENTS[key] || key.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

export function getAgentColor(agentName: string): string {
  const agent = agentName.replace(/_analyzer$/, '')
  switch (agent) {
    case 'cicd':
      return 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400'
    case 'kubernetes':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400'
    case 'observability':
      return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400'
  }
}

export function getAgentIcon(agent: string): string {
  switch (agent) {
    case 'cicd':
      return 'github-branch'
    case 'kubernetes':
      return 'boxes'
    case 'observability':
      return 'activity'
    default:
      return 'cpu'
  }
}

export function formatConfidence(confidence: number): string {
  return `${Math.round(confidence * 100)}%`
}

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.9) return 'text-green-600 dark:text-green-400'
  if (confidence >= 0.75) return 'text-blue-600 dark:text-blue-400'
  if (confidence >= 0.5) return 'text-yellow-600 dark:text-yellow-400'
  if (confidence >= 0.25) return 'text-orange-600 dark:text-orange-400'
  return 'text-red-600 dark:text-red-400'
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.slice(0, length) + '...'
}
