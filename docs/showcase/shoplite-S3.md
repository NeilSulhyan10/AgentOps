# Flow report: shoplite-S3

**ShopLite high latency and 5xx spike — P99 > 2950ms, error rate 41%**

- Result: Root cause: traffic_incident (confidence 0.88, status completed).
- Decisions made by: `rules`
- Investigation id: `e6b121ea-6184-4829-811e-a76ab8ab111f`

## Steps that need attention

None. Every step of the investigation ran cleanly.

## Where the fault is in the application

_green = fine · amber = worth a look · red = the fault · grey dashed = not visited_

```mermaid
flowchart LR
    cicd["CI/CD pipeline<br/>build, tests, deploy<br/>not checked"]:::skipped
    config["Configuration<br/>env vars, secrets, probes<br/>not checked"]:::skipped
    kubernetes["Kubernetes<br/>pods, memory limits, restarts<br/>checked, nothing found"]:::ok
    service["Service<br/>latency, error rate, logs<br/>traffic_incident (0.85)"]:::warning
    traffic["Traffic<br/>user load<br/>ROOT CAUSE: traffic_incident"]:::error
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
    load_evidence["load_evidence<br/>collect CI/CD, Kubernetes, observability evidence<br/>Load evidence (20 items)"]:::ok
    spawn_agent["spawn_agent<br/>create a specialist if none covers a problem<br/>ran, nothing to do"]:::ok
    route["route<br/>choose the next specialist<br/>visited 2 times"]:::ok
    invoke_agent["invoke_agent<br/>run that specialist<br/>ran: observability_analyzer, kubernetes_analyzer"]:::ok
    evaluate["evaluate<br/>is confidence high enough?<br/>visited 2 times"]:::ok
    critique["critique<br/>critic reviews the conclusion<br/>visited 2 times"]:::ok
    generate_rca["generate_rca<br/>write root cause + remediation<br/>Root cause: traffic_incident (0.88)"]:::ok
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
| 1 | ✔ | `normalize` | Start investigation | Incident shoplite-S3: ShopLite high latency and 5xx spike — P99 > 2950ms, error rate 41%<br>Decisions made by: rules |
| 2 | ✔ | `pre_filter` | Keyword pre-filter | First guess: traffic_incident<br>Wants to know about: observability_metrics, traffic_pattern |
| 3 | ✔ | `load_evidence` | Load evidence (20 items) | Sources: cicd_fixture, kubernetes_fixture, observability_fixture |
| 4 | ✔ | `route` | Route #1 -> observability_analyzer | Hypothesis 'traffic_incident' maps to observability_analyzer |
| 5 | ✔ | `invoke_agent` | observability_analyzer: traffic_incident (0.85) | Requests are slow (p99 2950 ms) and 41.2% of them fail<br>Evidence cited: 4, of which real: 4 |
| 6 | ✔ | `evaluate` | Confidence 0.88 / 0.75 (enough) | Per agent: observability_analyzer 0.88 |
| 7 | ✔ | `critique` | Critic #1: challenged (0.60) | The 'traffic_incident' conclusion rests on a single layer (observability_analyzer); nothing independent corroborates it.<br>Sent back to the router; suggested agent: kubernetes_analyzer |
| 8 | ✔ | `route` | Route #2 -> kubernetes_analyzer | Critic challenged the conclusion and suggested kubernetes_analyzer |
| 9 | ✔ | `invoke_agent` | kubernetes_analyzer: unknown (0.30) | Pods look healthy: exit code 0, 0 restarts, memory at most 21% of the limit<br>Evidence cited: 6, of which real: 6 |
| 10 | ✔ | `evaluate` | Confidence 0.88 / 0.75 (enough) | Per agent: observability_analyzer 0.88, kubernetes_analyzer 0.61 |
| 11 | ✔ | `critique` | Critic #2: confirmed (0.85) |  |
| 12 | ✔ | `generate_rca` | Root cause: traffic_incident (0.88) | Agents used: observability_analyzer -> kubernetes_analyzer |
| 13 | ✔ | `persist` | Finished: completed |  |
