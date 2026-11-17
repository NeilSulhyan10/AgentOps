# Flow report: shoplite-S2

**ShopLite pods OOMKilled repeatedly — memory limit 128Mi exceeded**

- Result: Root cause: unknown (confidence 0.00, status max_iterations_reached).
- Decisions made by: `rules+fault:ungrounded_finding`
- Investigation id: `be75b263-7d61-4072-85a3-66edd12adbe9`
- Injected fault (demo): `ungrounded_finding`

## Steps that need attention

- ⚠ **invoke_agent** - kubernetes_analyzer: deployment_induced_failure (0.95)
  - A recent deployment broke the service.
  - Evidence cited: 2, of which real: 0
  - The finding cites evidence ids that do not exist, so it is ignored when computing confidence.
- ⚠ **invoke_agent** - cicd_analyzer: deployment_induced_failure (0.95)
  - A recent deployment broke the service.
  - Evidence cited: 2, of which real: 0
  - The finding cites evidence ids that do not exist, so it is ignored when computing confidence.
- ⚠ **invoke_agent** - config_analyzer: deployment_induced_failure (0.95)
  - A recent deployment broke the service.
  - Evidence cited: 2, of which real: 0
  - The finding cites evidence ids that do not exist, so it is ignored when computing confidence.
- ⚠ **invoke_agent** - dependency_analyzer: deployment_induced_failure (0.95)
  - A recent deployment broke the service.
  - Evidence cited: 2, of which real: 0
  - The finding cites evidence ids that do not exist, so it is ignored when computing confidence.
- ⚠ **invoke_agent** - observability_analyzer: deployment_induced_failure (0.95)
  - A recent deployment broke the service.
  - Evidence cited: 2, of which real: 0
  - The finding cites evidence ids that do not exist, so it is ignored when computing confidence.
- ⚠ **critique** - Critic #1: challenged (0.20)
  - No finding cites evidence that exists in this investigation.
  - Could not loop back (no rounds, iterations or unused agents left); the root cause is reported with this concern unresolved.
- ⚠ **generate_rca** - Root cause: unknown (0.00)
  - Agents used: kubernetes_analyzer -> cicd_analyzer -> config_analyzer -> dependency_analyzer -> observability_analyzer
  - The investigation ran out of iterations before reaching the confidence threshold.

## Where the fault is in the application

_green = fine · amber = worth a look · red = the fault · grey dashed = not visited_

```mermaid
flowchart LR
    cicd["CI/CD pipeline<br/>build, tests, deploy<br/>checked, nothing found"]:::ok
    config["Configuration<br/>env vars, secrets, probes<br/>checked, nothing found"]:::ok
    kubernetes["Kubernetes<br/>pods, memory limits, restarts<br/>checked, nothing found"]:::ok
    service["Service<br/>latency, error rate, logs<br/>checked, nothing found"]:::ok
    traffic["Traffic<br/>user load<br/>not checked"]:::skipped
    dependency["Dependencies<br/>database, downstream services<br/>checked, nothing found"]:::ok
    cicd --> kubernetes
    config --> kubernetes
    kubernetes --> service
    traffic --> service
    service --> dependency
    classDef ok fill:#d1f2d9,stroke:#1a7f37,color:#0b2e13
    classDef warning fill:#fff1c2,stroke:#9a6700,color:#3b2a00
    classDef error fill:#ffd7d5,stroke:#cf222e,color:#5c0a0f,stroke-width:3px
    classDef skipped fill:#f3f3f3,stroke:#999999,color:#666666,stroke-dasharray:4 3
```

## How the investigation ran

_Thick arrows are the path that was taken._

```mermaid
flowchart TD
    normalize["normalize<br/>mark investigation as running<br/>Start investigation"]:::ok
    pre_filter["pre_filter<br/>keyword-based first guess<br/>Keyword pre-filter"]:::ok
    load_evidence["load_evidence<br/>collect CI/CD, Kubernetes, observability evidence<br/>Load evidence (22 items)"]:::ok
    spawn_agent["spawn_agent<br/>create a specialist if none covers a problem<br/>ran, nothing to do"]:::ok
    route["route<br/>choose the next specialist<br/>visited 5 times"]:::ok
    invoke_agent["invoke_agent<br/>run that specialist<br/>ran: kubernetes_analyzer, cicd_analyzer, config_analyzer, dependency_a"]:::warning
    evaluate["evaluate<br/>is confidence high enough?<br/>visited 5 times"]:::ok
    critique["critique<br/>critic reviews the conclusion<br/>Critic 1: challenged (0.20)"]:::warning
    generate_rca["generate_rca<br/>write root cause + remediation<br/>Root cause: unknown (0.00)"]:::warning
    persist["persist<br/>finish<br/>Finished: max_iterations_reached"]:::ok
    normalize --> pre_filter
    pre_filter --> load_evidence
    load_evidence --> spawn_agent
    spawn_agent --> route
    route --> invoke_agent
    route --> generate_rca
    invoke_agent --> evaluate
    evaluate --> route
    evaluate --> critique
    critique --> spawn_agent
    critique --> generate_rca
    generate_rca --> persist
    linkStyle 0,1,2,3,4,6,7,8,10,11 stroke-width:3px
    classDef ok fill:#d1f2d9,stroke:#1a7f37,color:#0b2e13
    classDef warning fill:#fff1c2,stroke:#9a6700,color:#3b2a00
    classDef error fill:#ffd7d5,stroke:#cf222e,color:#5c0a0f,stroke-width:3px
    classDef skipped fill:#f3f3f3,stroke:#999999,color:#666666,stroke-dasharray:4 3
```

## Step by step

| # | | Node | What happened | Details |
|---|---|---|---|---|
| 1 | ✔ | `normalize` | Start investigation | Incident shoplite-S2: ShopLite pods OOMKilled repeatedly — memory limit 128Mi exceeded<br>Decisions made by: rules+fault:ungrounded_finding<br>Injected fault for this demo run: ungrounded_finding |
| 2 | ✔ | `pre_filter` | Keyword pre-filter | First guess: kubernetes_oom<br>Wants to know about: deployment_details, pod_memory_status, pod_restart_pattern |
| 3 | ✔ | `load_evidence` | Load evidence (22 items) | Sources: cicd_fixture, kubernetes_fixture, observability_fixture |
| 4 | ✔ | `route` | Route #1 -> kubernetes_analyzer | Hypothesis 'kubernetes_oom' maps to kubernetes_analyzer |
| 5 | ⚠ | `invoke_agent` | kubernetes_analyzer: deployment_induced_failure (0.95) | A recent deployment broke the service.<br>Evidence cited: 2, of which real: 0<br>The finding cites evidence ids that do not exist, so it is ignored when computing confidence. |
| 6 | ✔ | `evaluate` | Confidence 0.00 / 0.75 (not enough yet) |  |
| 7 | ✔ | `route` | Route #2 -> cicd_analyzer | Recent finding suggests deployment_induced_failure; routing to cicd_analyzer |
| 8 | ⚠ | `invoke_agent` | cicd_analyzer: deployment_induced_failure (0.95) | A recent deployment broke the service.<br>Evidence cited: 2, of which real: 0<br>The finding cites evidence ids that do not exist, so it is ignored when computing confidence. |
| 9 | ✔ | `evaluate` | Confidence 0.00 / 0.75 (not enough yet) |  |
| 10 | ✔ | `route` | Route #3 -> config_analyzer | Default selection: config_analyzer |
| 11 | ⚠ | `invoke_agent` | config_analyzer: deployment_induced_failure (0.95) | A recent deployment broke the service.<br>Evidence cited: 2, of which real: 0<br>The finding cites evidence ids that do not exist, so it is ignored when computing confidence. |
| 12 | ✔ | `evaluate` | Confidence 0.00 / 0.75 (not enough yet) |  |
| 13 | ✔ | `route` | Route #4 -> dependency_analyzer | Default selection: dependency_analyzer |
| 14 | ⚠ | `invoke_agent` | dependency_analyzer: deployment_induced_failure (0.95) | A recent deployment broke the service.<br>Evidence cited: 2, of which real: 0<br>The finding cites evidence ids that do not exist, so it is ignored when computing confidence. |
| 15 | ✔ | `evaluate` | Confidence 0.00 / 0.75 (not enough yet) |  |
| 16 | ✔ | `route` | Route #5 -> observability_analyzer | Default selection: observability_analyzer |
| 17 | ⚠ | `invoke_agent` | observability_analyzer: deployment_induced_failure (0.95) | A recent deployment broke the service.<br>Evidence cited: 2, of which real: 0<br>The finding cites evidence ids that do not exist, so it is ignored when computing confidence. |
| 18 | ✔ | `evaluate` | Confidence 0.00 / 0.75 (not enough yet) |  |
| 19 | ⚠ | `critique` | Critic #1: challenged (0.20) | No finding cites evidence that exists in this investigation.<br>Could not loop back (no rounds, iterations or unused agents left); the root cause is reported with this concern unresolved. |
| 20 | ⚠ | `generate_rca` | Root cause: unknown (0.00) | Agents used: kubernetes_analyzer -> cicd_analyzer -> config_analyzer -> dependency_analyzer -> observability_analyzer<br>The investigation ran out of iterations before reaching the confidence threshold. |
| 21 | ✔ | `persist` | Finished: max_iterations_reached |  |
