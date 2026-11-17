export interface Run {
  investigation_id: string
  incident_id: string
  status: string
  root_cause_type: string | null
  confidence: number
  agents_invoked: string[]
  iterations: number
  created_at: string
  completed_at: string | null
  duration_s: number | null
  matches_expected: boolean | null      // null: unknown (no ground truth, or the run has not finished)
}

export interface AppScenario {
  scenario_id: string
  title: string
  severity: string
  expected_root_cause: string | null
  runs: Run[]
}

export interface AppPage {
  key: string
  name: string
  description: string
  scenarios: AppScenario[]
}

export interface AppSummary {
  key: string
  name: string
  description: string
  scenario_count: number
  run_count: number
  last_run: Run | null
}
