# Flow report: shoplite-S7

**ShopLite routine health check — no anomalies detected**

- Result: Root cause: unknown (confidence 0.30, status completed).
- Decisions made by: `rules`
- Investigation id: `03b438f2-b7f9-4099-99a7-25517be67b1e`

## Steps that need attention

None. Every step of the investigation ran cleanly.

## Where the fault is in the application

_green = fine · amber = worth a look · red = the fault · grey dashed = not visited_

```mermaid
flowchart LR
    cicd["CI/CD pipeline<br/>build, tests, deploy<br/>checked, nothing found"]:::ok
    config["Configuration<br/>env vars, secrets, probes<br/>not checked"]:::skipped
    kubernetes["Kubernetes<br/>pods, memory limits, restarts<br/>not checked"]:::skipped
    service["Service<br/>latency, error rate, logs<br/>checked, nothing found"]:::ok
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
    load_evidence["load_evidence<br/>collect CI/CD, Kubernetes, observability evidence<br/>Load evidence (16 items)"]:::ok
    spawn_agent["spawn_agent<br/>create a specialist if none covers a problem<br/>ran, nothing to do"]:::ok
    route["route<br/>choose the next specialist<br/>visited 2 times"]:::ok
    invoke_agent["invoke_agent<br/>run that specialist<br/>ran: cicd_analyzer, observability_analyzer"]:::ok
    evaluate["evaluate<br/>is confidence high enough?<br/>visited 2 times"]:::ok
    critique["critique<br/>critic reviews the conclusion<br/>Critic 1: confirmed (0.30)"]:::ok
    generate_rca["generate_rca<br/>write root cause + remediation<br/>Root cause: unknown (0.30)"]:::ok
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
    linkStyle 0,1,2,3,4,6,7,8,10,11 stroke-width:3px
    classDef ok fill:#d1f2d9,stroke:#1a7f37,color:#0b2e13
    classDef warning fill:#fff1c2,stroke:#9a6700,color:#3b2a00
    classDef error fill:#ffd7d5,stroke:#cf222e,color:#5c0a0f,stroke-width:3px
    classDef skipped fill:#f3f3f3,stroke:#999999,color:#666666,stroke-dasharray:4 3
```

## Step by step

| # | | Node | What happened | Details |
|---|---|---|---|---|
| 1 | ✔ | `normalize` | Start investigation | Incident shoplite-S7: ShopLite routine health check — no anomalies detected<br>Decisions made by: rules |
| 2 | ✔ | `pre_filter` | Keyword pre-filter | First guess: deployment_induced_failure<br>Wants to know about: deployment_details, observability_metrics |
| 3 | ✔ | `load_evidence` | Load evidence (16 items) | Sources: cicd_fixture, kubernetes_fixture, observability_fixture |
| 4 | ✔ | `route` | Route #1 -> cicd_analyzer | Hypothesis 'deployment_induced_failure' maps to cicd_analyzer |
| 5 | ✔ | `invoke_agent` | cicd_analyzer: unknown (0.30) | The deployment re-used the same image and changed nothing; CI/CD does not explain the incident<br>Evidence cited: 1, of which real: 1 |
| 6 | ✔ | `evaluate` | Confidence 0.25 / 0.75 (not enough yet) | Per agent: cicd_analyzer 0.46 |
| 7 | ✔ | `route` | Route #2 -> observability_analyzer | Evidence gap 'observability_metrics' maps to observability_analyzer |
| 8 | ✔ | `invoke_agent` | observability_analyzer: unknown (0.30) | Metrics look normal: p99 14 ms, error rate 0%, no error logs<br>Evidence cited: 6, of which real: 6 |
| 9 | ✔ | `evaluate` | Confidence 0.30 / 0.75 (enough) | Per agent: cicd_analyzer 0.46, observability_analyzer 0.58 |
| 10 | ✔ | `critique` | Critic #1: confirmed (0.30) |  |
| 11 | ✔ | `generate_rca` | Root cause: unknown (0.30) | Agents used: cicd_analyzer -> observability_analyzer |
| 12 | ✔ | `persist` | Finished: completed |  |
