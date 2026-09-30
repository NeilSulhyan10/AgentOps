import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { incidentApi } from '../api/client'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { Input } from '../components/ui/Input'
import { Textarea } from '../components/ui/Textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/Select'
import { AlertCircle, CheckCircle, Loader2, ArrowLeft } from 'lucide-react'

export function IncidentCreate() {
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [formData, setFormData] = useState({
    incident_id: '',
    title: '',
    description: '',
    severity: 'critical' as const,
    status: 'open' as const,
    source: 'manual' as const,
    service_name: '',
    namespace: 'production',
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setIsLoading(true)

    try {
      const response = await incidentApi.create({
        incident_id: formData.incident_id,
        title: formData.title,
        description: formData.description,
        severity: formData.severity,
        status: formData.status,
        source: formData.source,
        service_name: formData.service_name,
        namespace: formData.namespace,
      })
      setSuccess(true)
      setTimeout(() => {
        navigate(`/investigation/${response.investigation_id}`)
      }, 1500)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create incident')
    } finally {
      setIsLoading(false)
    }
  }

  const handleChange = (field: string, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }))
  }

  if (success) {
    return (
      <Card className="max-w-2xl mx-auto mt-8">
        <CardContent className="pt-6 text-center">
          <div className="flex items-center justify-center gap-3 text-green-600 dark:text-green-400 mb-4">
            <CheckCircle className="h-12 w-12 animate-bounce" />
            <span className="text-2xl font-bold">Incident Created!</span>
          </div>
          <p className="text-dark-500 dark:text-dark-400">Redirecting to investigation...</p>
          <Loader2 className="h-8 w-8 animate-spin text-primary-600 mx-auto mt-4" />
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate('/')}>
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-dark-900 dark:text-dark-100">Create Incident</h1>
          <p className="text-dark-500 dark:text-dark-400">Report a new incident for investigation</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Incident Details</CardTitle>
          <CardDescription>Provide details about the incident to start an investigation</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="flex items-center gap-3 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0" />
                <p className="text-red-600 dark:text-red-400">{error}</p>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label htmlFor="incident_id" className="block text-sm font-medium text-dark-700 dark:text-dark-300 mb-1">
                  Incident ID <span className="text-red-500">*</span>
                </label>
                <Input
                  id="incident_id"
                  value={formData.incident_id}
                  onChange={(e) => handleChange('incident_id', e.target.value)}
                  placeholder="e.g., incident-001"
                  required
                  disabled={isLoading}
                />
                <p className="mt-1 text-xs text-dark-500">Unique identifier for this incident</p>
              </div>

              <div>
                <label htmlFor="title" className="block text-sm font-medium text-dark-700 dark:text-dark-300 mb-1">
                  Title <span className="text-red-500">*</span>
                </label>
                <Input
                  id="title"
                  value={formData.title}
                  onChange={(e) => handleChange('title', e.target.value)}
                  placeholder="e.g., Payment API 5xx rate increased"
                  required
                  disabled={isLoading}
                />
              </div>
            </div>

            <div>
              <label htmlFor="description" className="block text-sm font-medium text-dark-700 dark:text-dark-300 mb-1">
                Description <span className="text-red-500">*</span>
              </label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => handleChange('description', e.target.value)}
                placeholder="Describe the incident, including symptoms, affected services, and any relevant context..."
                rows={4}
                required
                disabled={isLoading}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <div>
                <label htmlFor="severity" className="block text-sm font-medium text-dark-700 dark:text-dark-300 mb-1">
                  Severity
                </label>
                <Select value={formData.severity} onValueChange={(v) => handleChange('severity', v)} disabled={isLoading}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select severity" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low"><Badge variant="secondary">Low</Badge></SelectItem>
                    <SelectItem value="medium"><Badge variant="default">Medium</Badge></SelectItem>
                    <SelectItem value="high"><Badge variant="destructive">High</Badge></SelectItem>
                    <SelectItem value="critical"><Badge variant="destructive" className="bg-red-600">Critical</Badge></SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label htmlFor="source" className="block text-sm font-medium text-dark-700 dark:text-dark-300 mb-1">
                  Source
                </label>
                <Select value={formData.source} onValueChange={(v) => handleChange('source', v)} disabled={isLoading}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select source" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manual">Manual Report</SelectItem>
                    <SelectItem value="prometheus-alert">Prometheus Alert</SelectItem>
                    <SelectItem value="datadog-alert">Datadog Alert</SelectItem>
                    <SelectItem value="pagerduty">PagerDuty</SelectItem>
                    <SelectItem value="grafana-alert">Grafana Alert</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label htmlFor="service_name" className="block text-sm font-medium text-dark-700 dark:text-dark-300 mb-1">
                  Service Name <span className="text-red-500">*</span>
                </label>
                <Input
                  id="service_name"
                  value={formData.service_name}
                  onChange={(e) => handleChange('service_name', e.target.value)}
                  placeholder="e.g., payment-service"
                  required
                  disabled={isLoading}
                />
              </div>

              <div>
                <label htmlFor="namespace" className="block text-sm font-medium text-dark-700 dark:text-dark-300 mb-1">
                  Namespace
                </label>
                <Input
                  id="namespace"
                  value={formData.namespace}
                  onChange={(e) => handleChange('namespace', e.target.value)}
                  placeholder="e.g., production"
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="flex justify-end gap-4 pt-4 border-t border-dark-200 dark:border-dark-700">
              <Button type="button" variant="outline" onClick={() => navigate('/')} disabled={isLoading}>
                Cancel
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Creating...
                  </>
                ) : (
                  'Create Incident & Start Investigation'
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card className="bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800">
        <CardContent className="pt-6">
          <h3 className="text-sm font-semibold text-blue-800 dark:text-blue-200 mb-3">Tips for Effective Investigations</h3>
          <ul className="space-y-2 text-sm text-blue-700 dark:text-blue-300">
            <li className="flex items-start gap-2"><span className="text-blue-500">•</span> Include timestamps and error rates in the description</li>
            <li className="flex items-start gap-2"><span className="text-blue-500">•</span> Mention any recent deployments or configuration changes</li>
            <li className="flex items-start gap-2"><span className="text-blue-500">•</span> Specify the exact service name and Kubernetes namespace</li>
            <li className="flex items-start gap-2"><span className="text-blue-500">•</span> The system will automatically route to relevant specialist agents</li>
          </ul>
        </CardContent>
      </Card>
    </div>
  )
}