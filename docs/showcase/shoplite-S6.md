# Flow report: shoplite-S6

**ShopLite multi-layer failure — OOMKilled pods, high latency, high error rate**

- Result: Root cause: multi_layer_failure (confidence 0.99, status completed).
- Decisions made by: `rules`
- Investigation id: `7203050b-efa3-4d7b-beec-7601b9828dd6`

## Steps that need attention

None. Every step of the investigation ran cleanly.

## Where the fault is in the application

_green = fine · amber = worth a look · red = the fault · grey dashed = not visited_

```mermaid
flowchart LR
    cicd["CI/CD pipeline<br/>build, tests, deploy<br/>ROOT CAUSE: multi_layer_failure (0.90)"]:::error
    config["Configuration<br/>env vars, secrets, probes<br/>not checked"]:::skipped
    kubernetes["Kubernetes<br/>pods, memory limits, restarts<br/>ROOT CAUSE: multi_layer_failure (0.95)"]:::error
    service["Service<br/>latency, error rate, logs<br/>ROOT CAUSE: multi_layer_failure (0.85)"]:::error
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
    load_evidence["load_evidence<br/>collect CI/CD, Kubernetes, observability evidence<br/>Load evidence (23 items)"]:::ok
    spawn_agent["spawn_agent<br/>create a specialist if none covers a problem<br/>ran, nothing to do"]:::ok
    route["route<br/>choose the next specialist<br/>visited 3 times"]:::ok
    invoke_agent["invoke_agent<br/>run that specialist<br/>ran: kubernetes_analyzer, cicd_analyzer, observability_analyzer"]:::ok
    evaluate["evaluate<br/>is confidence high enough?<br/>visited 3 times"]:::ok
    critique["critique<br/>critic reviews the conclusion<br/>visited 3 times"]:::ok
    generate_rca["generate_rca<br/>write root cause + remediation<br/>Root cause: multi_layer_failure (0.99)"]:::ok
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
| 1 | ✔ | `normalize` | Start investigation | Incident shoplite-S6: ShopLite multi-layer failure — OOMKilled pods, high latency, high error rate<br>Decisions made by: rules |
| 2 | ✔ | `pre_filter` | Keyword pre-filter | First guess: kubernetes_oom<br>Wants to know about: deployment_details, pod_memory_status, pod_restart_pattern, observability_metrics |
| 3 | ✔ | `load_evidence` | Load evidence (23 items) | Sources: cicd_fixture, kubernetes_fixture, observability_fixture |
| 4 | ✔ | `route` | Route #1 -> kubernetes_analyzer | Hypothesis 'kubernetes_oom' maps to kubernetes_analyzer |
| 5 | ✔ | `invoke_agent` | kubernetes_analyzer: kubernetes_oom (0.95) | 2 pod(s) were OOMKilled (exit code 137): they used more memory than their limit allows<br>Evidence cited: 5, of which real: 5 |
| 6 | ✔ | `evaluate` | Confidence 0.83 / 0.75 (enough) | Per agent: kubernetes_analyzer 0.93 |
| 7 | ✔ | `critique` | Critic #1: challenged (0.60) | The 'kubernetes_oom' conclusion rests on a single layer (kubernetes_analyzer); nothing independent corroborates it.<br>The pre-filter flagged 'deployment_details' but cicd_analyzer has not looked at it yet.<br>Sent back to the router; suggested agent: cicd_analyzer |
| 8 | ✔ | `route` | Route #2 -> cicd_analyzer | Critic challenged the conclusion and suggested cicd_analyzer |
| 9 | ✔ | `invoke_agent` | cicd_analyzer: deployment_induced_failure (0.90) | A resource limit was changed in the release; the incident starts right after it: Config change: resources.limits.memory = 128Mi<br>Evidence cited: 2, of which real: 2 |
| 10 | ✔ | `evaluate` | Confidence 0.88 / 0.75 (enough) | Per agent: kubernetes_analyzer 0.93, cicd_analyzer 0.83 |
| 11 | ✔ | `critique` | Critic #2: challenged (0.60) | The pre-filter flagged 'observability_metrics' but observability_analyzer has not looked at it yet.<br>Sent back to the router; suggested agent: observability_analyzer |
| 12 | ✔ | `route` | Route #3 -> observability_analyzer | Critic challenged the conclusion and suggested observability_analyzer |
| 13 | ✔ | `invoke_agent` | observability_analyzer: traffic_incident (0.85) | Requests are slow (p99 3000 ms) and 78.3% of them fail<br>Evidence cited: 3, of which real: 3 |
| 14 | ✔ | `evaluate` | Confidence 0.99 / 0.75 (enough) | Per agent: kubernetes_analyzer 0.93, cicd_analyzer 0.83, observability_analyzer 0.88 |
| 15 | ✔ | `critique` | Critic #3: confirmed (0.95) |  |
| 16 | ✔ | `generate_rca` | Root cause: multi_layer_failure (0.99) | Agents used: kubernetes_analyzer -> cicd_analyzer -> observability_analyzer |
| 17 | ✔ | `persist` | Finished: completed |  |
