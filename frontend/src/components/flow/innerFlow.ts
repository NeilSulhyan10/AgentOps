import type { FlowEvent, FlowStatus, FlowStep } from '../../types/flow'

export interface Stage {
  label: string            // small caps heading of the box
  lines: string[]          // what is in the box
  tone: FlowStatus         // ok = green, warning = amber, error = red, skipped = neutral grey
}

const list = (items: unknown, none = 'none') =>
  Array.isArray(items) && items.length ? items.map(String).join(', ') : none

const pct = (n: unknown) => (typeof n === 'number' ? n.toFixed(2) : '?')

/** The main event of a step: the one that is not a "the LLM's answer was unusable" notice. */
export const mainEvent = (step: FlowStep): FlowEvent | undefined =>
  step.events.find((e) => e.event !== 'llm_parse_fallback' && e.event !== 'llm_call') ?? step.events[0]

/**
 * "Inside this step": the step opened up as inputs -> decision -> output boxes.
 * Built from the flow-log events, so it shows what really happened, not what should have.
 */
export function innerFlow(step: FlowStep, engine: string): Stage[] {
  const e = mainEvent(step) ?? ({ event: '' } as FlowEvent)
  const fallback = step.events.find((x) => x.event === 'llm_parse_fallback')
  const neutral: FlowStatus = 'skipped'
  const verdictTone: FlowStatus = step.status === 'error' ? 'error' : step.status === 'warning' ? 'warning' : 'ok'

  if (e.event === 'node_failed') {
    return [{ label: 'Was running', lines: [step.node + (e.agent ? ` (${e.agent})` : '')], tone: neutral },
            { label: 'Crashed with', lines: [String(e.error ?? 'unknown error')], tone: 'error' },
            { label: 'Result', lines: ['The investigation stopped here and is marked failed'], tone: 'error' }]
  }

  switch (step.node) {
    case 'normalize':
      return [{ label: 'Incident', lines: [String(e.title ?? step.title), `Engine: ${engine || 'rules'}`], tone: neutral },
              { label: 'Result', lines: ['Investigation marked as running'], tone: 'ok' }]

    case 'pre_filter':
      return [{ label: 'Reads', lines: ['Incident title and description', 'Ignores words after "no" / "not"'], tone: neutral },
              { label: 'First guess', lines: [String(e.hypothesis ?? 'unknown')], tone: 'ok' },
              { label: 'Wants to know about', lines: [list(e.evidence_gaps)], tone: 'ok' }]

    case 'load_evidence':
      return [{ label: 'Collects', lines: ['CI/CD, Kubernetes, observability'], tone: neutral },
              { label: 'Sources', lines: [list(e.sources, 'no sources')], tone: e.total_evidence ? 'ok' : 'warning' },
              { label: 'Result', lines: [`${e.total_evidence ?? 0} evidence items`], tone: e.total_evidence ? 'ok' : 'warning' }]

    case 'spawn_agent':
      return [{ label: 'Nobody covers', lines: [String(e.reason ?? '')], tone: 'warning' },
              { label: 'Spawned', lines: [String(e.agent ?? ''), String(e.description ?? '')], tone: 'ok' },
              { label: 'Will look for', lines: [list(e.keywords)], tone: 'ok' },
              { label: 'Sits in layer', lines: [String(e.layer ?? '')], tone: 'ok' }]

    case 'route': {
      if (e.event === 'route_stopped')
        return [{ label: 'Stopped', lines: [`Reason: ${e.reason}`, `Iteration ${e.iteration}`], tone: 'warning' }]
      const decider = e.llm_choice
        ? (e.used_deterministic_fallback ? `LLM suggested "${e.llm_choice}": not available, rejected` : `LLM chose "${e.llm_choice}"`)
        : 'No LLM answer: rules decided'
      return [
        { label: 'Looks at', lines: [`First guess: ${e.hypothesis ?? 'unknown'}`, `Gaps: ${list(e.evidence_gaps)}`, `Already ran: ${list(e.agents_invoked)}`], tone: neutral },
        { label: 'Candidates', lines: [list(e.available_agents)], tone: neutral },
        { label: 'Decision', lines: [decider], tone: fallback || e.used_deterministic_fallback ? 'warning' : 'ok' },
        { label: 'Chosen', lines: [String(e.selected_agent ?? ''), String(e.reasoning ?? '')], tone: 'ok' },
      ]
    }

    case 'invoke_agent': {
      const cited = Number(e.cited_evidence ?? 0)
      const real = Number(e.grounded_evidence ?? 0)
      const ungrounded = cited > 0 && real === 0
      return [
        { label: 'Specialist', lines: [String(e.agent ?? ''), fallback ? 'LLM answer unusable: rules took over' : `Engine: ${engine || 'rules'}`], tone: fallback ? 'warning' : neutral },
        { label: 'Finding', lines: [String(e.hypothesis ?? 'unknown'), `confidence ${pct(e.confidence)}`, String(e.finding ?? '')], tone: 'ok' },
        { label: 'Evidence check', lines: [`cites ${cited} item(s)`, `${real} actually exist`], tone: ungrounded ? 'warning' : cited === 0 ? 'warning' : 'ok' },
        { label: 'Counts toward confidence?', lines: [real > 0 ? 'Yes' : 'No: cites no real evidence, so it is ignored'], tone: real > 0 ? 'ok' : 'warning' },
      ]
    }

    case 'evaluate': {
      const per = (e.agent_confidences ?? {}) as Record<string, number>
      return [
        { label: 'Grounded confidences', lines: Object.entries(per).map(([a, c]) => `${a}: ${pct(c)}`).concat(Object.keys(per).length ? [] : ['none yet']), tone: neutral },
        { label: 'Overall (highest)', lines: [pct(e.overall_confidence)], tone: 'ok' },
        { label: 'Threshold', lines: [pct(e.threshold)], tone: neutral },
        { label: 'Decision', lines: [e.all_clear ? 'Everyone found nothing wrong: stop' : e.is_sufficient ? 'Enough: go to the critic' : 'Not enough: ask another specialist'], tone: e.is_sufficient ? 'ok' : 'warning' },
      ]
    }

    case 'critique': {
      const concerns = (e.concerns ?? []) as string[]
      return [
        { label: 'Reviewed', lines: [`Round ${e.round}`, `Leading idea: ${e.hypothesis ?? 'unknown'}`], tone: neutral },
        { label: 'Concerns', lines: concerns.length ? concerns : ['none'], tone: concerns.length ? (e.looping_back ? 'ok' : 'warning') : 'ok' },
        { label: 'Verdict', lines: [String(e.verdict ?? ''), `confidence ${pct(e.confidence)}`], tone: verdictTone },
        { label: 'Outcome', lines: [e.verdict === 'challenged'
            ? (e.looping_back ? `Sent back to route (suggested: ${e.suggested_agent ?? 'none'})` : 'Nothing left to try: report goes out with the concern attached')
            : 'Report goes on to the root-cause step'], tone: verdictTone },
      ]
    }

    case 'generate_rca':
      return [
        { label: 'Specialists used', lines: [list(e.agents_invoked)], tone: neutral },
        { label: 'Decides the type', lines: ['mechanism > trigger > symptom', 'several mechanisms + a trigger = multi-layer'], tone: neutral },
        { label: 'Root cause', lines: [String(e.root_cause_type ?? 'unknown'), `confidence ${pct(e.overall_confidence)}`], tone: verdictTone },
        { label: 'Run ended as', lines: [String(e.status ?? ''), `${e.iterations ?? '?'} iteration(s), ${e.critic_rounds ?? 0} critic round(s)`], tone: verdictTone },
      ]

    case 'persist':
      return [{ label: 'Finished', lines: [`Status: ${e.status ?? ''}`, e.duration_ms ? `${e.duration_ms} ms in total` : ''].filter(Boolean), tone: 'ok' }]

    default:
      return [{ label: step.node, lines: [step.title], tone: verdictTone }]
  }
}
