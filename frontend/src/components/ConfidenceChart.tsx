import { useMemo } from 'react'
import {
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  AreaChart,
  Area,
} from 'recharts'
import { Card, CardHeader, CardTitle, CardContent } from './ui/Card'
import type { ConfidenceEntry, AgentType } from '../types'

interface ConfidenceChartProps {
  confidenceHistory: ConfidenceEntry[]
}

export function ConfidenceChart({ confidenceHistory }: ConfidenceChartProps) {
  const chartData = useMemo(() => {
    if (!confidenceHistory || confidenceHistory.length === 0) return []

    return confidenceHistory.map((entry, idx) => {
      const agentConfidences = entry.agent_confidences || {}
      const agents = Object.keys(agentConfidences).sort()
      
      return {
        iteration: idx + 1,
        overall: Math.round(entry.overall_confidence * 100),
        ...Object.fromEntries(
          agents.map(agent => [agent, Math.round((agentConfidences[agent as AgentType] || 0) * 100)])
        ),
      }
    })
  }, [confidenceHistory])

  const agents = useMemo(() => {
    if (!confidenceHistory || confidenceHistory.length === 0) return []
    const allAgents = new Set<string>()
    confidenceHistory.forEach(entry => {
      Object.keys(entry.agent_confidences || {}).forEach(agent => allAgents.add(agent))
    })
    return Array.from(allAgents).sort()
  }, [confidenceHistory])

  if (chartData.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Confidence Progression</CardTitle>
        </CardHeader>
        <CardContent className="h-64 flex items-center justify-center">
          <p className="text-dark-500 dark:text-dark-400">No confidence data available</p>
        </CardContent>
      </Card>
    )
  }

  const colors = {
    overall: '#3b82f6',
    cicd: '#10b981',
    kubernetes: '#f59e0b',
    observability: '#8b5cf6',
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Confidence Progression</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <defs>
                {agents.map((agent) => (
                  <linearGradient id={`color-${agent}`} key={agent} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={colors[agent as keyof typeof colors] || '#888'} stopOpacity={0.3} />
                    <stop offset="95%" stopColor={colors[agent as keyof typeof colors] || '#888'} stopOpacity={0} />
                  </linearGradient>
                ))}
                <linearGradient id="color-overall" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={colors.overall} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={colors.overall} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" vertical={false} />
              <XAxis
                dataKey="iteration"
                tickLine={false}
                axisLine={false}
                tick={{ fill: '#6b7280', fontSize: 12 }}
                tickFormatter={(value) => `Iter ${value}`}
              />
              <YAxis
                domain={[0, 100]}
                tickLine={false}
                axisLine={false}
                tick={{ fill: '#6b7280', fontSize: 12 }}
                tickFormatter={(value) => `${value}%`}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#fff',
                  border: '1px solid #e5e7eb',
                  borderRadius: '8px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                }}
              />
              <Legend />
              {agents.map((agent) => (
                <Area
                  key={agent}
                  type="monotone"
                  dataKey={agent}
                  stroke={colors[agent as keyof typeof colors] || '#888'}
                  fill={`url(#color-${agent})`}
                  strokeWidth={2}
                  name={agent.toUpperCase()}
                />
              ))}
              <Line
                type="monotone"
                dataKey="overall"
                stroke={colors.overall}
                strokeWidth={3}
                dot={{ fill: colors.overall, strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6, strokeWidth: 2 }}
                name="Overall"
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-wrap gap-4 mt-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <span className="text-dark-700 dark:text-dark-300 font-medium">Overall</span>
          </div>
          {agents.map((agent) => (
            <div key={agent} className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: colors[agent as keyof typeof colors] || '#888' }}
              />
              <span className="text-dark-700 dark:text-dark-300 font-medium capitalize">{agent}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}