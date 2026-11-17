# Flow report: shoplite-S5

**ShopLite 100% error rate — database dependency unreachable**

- Result: Root cause: dependency_issue (confidence 0.93, status completed).
- Decisions made by: `rules`
- Investigation id: `c1bd6c64-7403-473a-b012-e4889f276bb0`

## Steps that need attention

None. Every step of the investigation ran cleanly.

## Where the fault is in the application

_green = fine · amber = worth a look · red = the fault · grey dashed = not visited_

```mermaid
flowchart LR
    cicd["CI/CD pipeline<br/>build, tests, deploy<br/>dependency_issue (0.70)"]:::warning
    config["Configuration<br/>env vars, secrets, probes<br/>not checked"]:::skipped
    kubernetes["Kubernetes<br/>pods, memory limits, restarts<br/>not checked"]:::skipped
    service["Service<br/>latency, error rate, logs<br/>dependency_issue (0.90)"]:::warning
    traffic["Traffic<br/>user load<br/>not checked"]:::skipped
    dependency["Dependencies<br/>database, downstream services<br/>ROOT CAUSE: dependency_issue (0.65)"]:::error
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
    route["route<br/>choose the next specialist<br/>visited 3 times"]:::ok
    invoke_agent["invoke_agent<br/>run that specialist<br/>ran: cicd_analyzer, dependency_analyzer, observability_analyzer"]:::ok
    evaluate["evaluate<br/>is confidence high enough?<br/>visited 3 times"]:::ok
    critique["critique<br/>critic reviews the conclusion<br/>Critic 1: confirmed (0.90)"]:::ok
    generate_rca["generate_rca<br/>write root cause + remediation<br/>Root cause: dependency_issue (0.93)"]:::ok
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
| 1 | ✔ | `normalize` | Start investigation | Incident shoplite-S5: ShopLite 100% error rate — database dependency unreachable<br>Decisions made by: rules |
| 2 | ✔ | `pre_filter` | Keyword pre-filter | First guess: deployment_induced_failure<br>Wants to know about: deployment_details, observability_metrics, dependency_health |
| 3 | ✔ | `load_evidence` | Load evidence (20 items) | Sources: cicd_fixture, kubernetes_fixture, observability_fixture |
| 4 | ✔ | `route` | Route #1 -> cicd_analyzer | Hypothesis 'deployment_induced_failure' maps to cicd_analyzer |
| 5 | ✔ | `invoke_agent` | cicd_analyzer: dependency_issue (0.70) | The release touched a dependency: Config change: FAULT = db_down<br>Evidence cited: 1, of which real: 1 |
| 6 | ✔ | `evaluate` | Confidence 0.52 / 0.75 (not enough yet) | Per agent: cicd_analyzer 0.67 |
| 7 | ✔ | `route` | Route #2 -> dependency_analyzer | Recent finding suggests dependency_issue; routing to dependency_analyzer |
| 8 | ✔ | `invoke_agent` | dependency_analyzer: dependency_issue (0.65) | Failing dependencies - databases, caches, downstream services, libraries: Log: Database unreachable — cannot load products; Log: Database unreachable — cannot persist order; Trace db-trace-001: 6ms<br>Evidence cited: 3, of which real: 3 |
| 9 | ✔ | `evaluate` | Confidence 0.70 / 0.75 (not enough yet) | Per agent: cicd_analyzer 0.67, dependency_analyzer 0.75 |
| 10 | ✔ | `route` | Route #3 -> observability_analyzer | Evidence gap 'observability_metrics' maps to observability_analyzer |
| 11 | ✔ | `invoke_agent` | observability_analyzer: dependency_issue (0.90) | The service cannot reach something it depends on (Log: Database unreachable — cannot load products); error rate 100%, latency itself is 18 ms so the app is not overloaded<br>Evidence cited: 3, of which real: 3 |
| 12 | ✔ | `evaluate` | Confidence 0.93 / 0.75 (enough) | Per agent: cicd_analyzer 0.67, dependency_analyzer 0.75, observability_analyzer 0.88 |
| 13 | ✔ | `critique` | Critic #1: confirmed (0.90) |  |
| 14 | ✔ | `generate_rca` | Root cause: dependency_issue (0.93) | Agents used: cicd_analyzer -> dependency_analyzer -> observability_analyzer |
| 15 | ✔ | `persist` | Finished: completed |  |
