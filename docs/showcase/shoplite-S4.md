# Flow report: shoplite-S4

**ShopLite CrashLoopBackOff — startup failing due to missing env var**

- Result: Root cause: configuration_error (confidence 0.90, status completed).
- Decisions made by: `rules`
- Investigation id: `04b110dc-3e02-45f0-81b2-6b88b1cd7252`

## Steps that need attention

None. Every step of the investigation ran cleanly.

## Where the fault is in the application

_green = fine · amber = worth a look · red = the fault · grey dashed = not visited_

```mermaid
flowchart LR
    cicd["CI/CD pipeline<br/>build, tests, deploy<br/>configuration_error (0.90)"]:::warning
    config["Configuration<br/>env vars, secrets, probes<br/>ROOT CAUSE: configuration_error"]:::error
    kubernetes["Kubernetes<br/>pods, memory limits, restarts<br/>application_error (0.80)"]:::warning
    service["Service<br/>latency, error rate, logs<br/>not checked"]:::skipped
    traffic["Traffic<br/>user load<br/>not checked"]:::skipped
    dependency["Dependencies<br/>database, downstream services<br/>not checked"]:::skipped
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
    load_evidence["load_evidence<br/>collect CI/CD, Kubernetes, observability evidence<br/>Load evidence (18 items)"]:::ok
    spawn_agent["spawn_agent<br/>create a specialist if none covers a problem<br/>ran, nothing to do"]:::ok
    route["route<br/>choose the next specialist<br/>visited 2 times"]:::ok
    invoke_agent["invoke_agent<br/>run that specialist<br/>ran: cicd_analyzer, kubernetes_analyzer"]:::ok
    evaluate["evaluate<br/>is confidence high enough?<br/>visited 2 times"]:::ok
    critique["critique<br/>critic reviews the conclusion<br/>visited 2 times"]:::ok
    generate_rca["generate_rca<br/>write root cause + remediation<br/>Root cause: configuration_error (0.90)"]:::ok
    persist["persist<br/>finish<br/>Finished: completed"]:::ok
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
    linkStyle 0,1,2,3,4,6,8,9,10,11 stroke-width:3px
    classDef ok fill:#d1f2d9,stroke:#1a7f37,color:#0b2e13
    classDef warning fill:#fff1c2,stroke:#9a6700,color:#3b2a00
    classDef error fill:#ffd7d5,stroke:#cf222e,color:#5c0a0f,stroke-width:3px
    classDef skipped fill:#f3f3f3,stroke:#999999,color:#666666,stroke-dasharray:4 3
```

## Step by step

| # | | Node | What happened | Details |
|---|---|---|---|---|
| 1 | ✔ | `normalize` | Start investigation | Incident shoplite-S4: ShopLite CrashLoopBackOff — startup failing due to missing env var<br>Decisions made by: rules |
| 2 | ✔ | `pre_filter` | Keyword pre-filter | First guess: deployment_induced_failure<br>Wants to know about: deployment_details, pod_restart_pattern, configuration_changes |
| 3 | ✔ | `load_evidence` | Load evidence (18 items) | Sources: cicd_fixture, kubernetes_fixture, observability_fixture |
| 4 | ✔ | `route` | Route #1 -> cicd_analyzer | Hypothesis 'deployment_induced_failure' maps to cicd_analyzer |
| 5 | ✔ | `invoke_agent` | cicd_analyzer: configuration_error (0.90) | A required setting was removed or broken by the release: Config change: FAULT = bad_config<br>Evidence cited: 3, of which real: 3 |
| 6 | ✔ | `evaluate` | Confidence 0.85 / 0.75 (enough) | Per agent: cicd_analyzer 0.90 |
| 7 | ✔ | `critique` | Critic #1: challenged (0.60) | The 'configuration_error' conclusion rests on a single layer (cicd_analyzer); nothing independent corroborates it.<br>The pre-filter flagged 'pod_restart_pattern' but kubernetes_analyzer has not looked at it yet.<br>Sent back to the router; suggested agent: kubernetes_analyzer |
| 8 | ✔ | `route` | Route #2 -> kubernetes_analyzer | Critic challenged the conclusion and suggested kubernetes_analyzer |
| 9 | ✔ | `invoke_agent` | kubernetes_analyzer: application_error (0.80) | 2 pod(s) crash on startup with exit code 1; memory is only at 4% of the limit, so this is not a resource problem<br>Evidence cited: 5, of which real: 5 |
| 10 | ✔ | `evaluate` | Confidence 0.90 / 0.75 (enough) | Per agent: cicd_analyzer 0.90, kubernetes_analyzer 0.85 |
| 11 | ✔ | `critique` | Critic #2: confirmed (0.90) |  |
| 12 | ✔ | `generate_rca` | Root cause: configuration_error (0.90) | Agents used: cicd_analyzer -> kubernetes_analyzer |
| 13 | ✔ | `persist` | Finished: completed |  |
