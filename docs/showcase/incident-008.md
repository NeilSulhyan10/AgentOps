# Flow report: incident-008

**Checkout latency and errors: Redis cache full and evicting keys**

- Result: Root cause: dependency_issue (confidence 0.78, status completed).
- Decisions made by: `rules`
- Investigation id: `b9a59892-ece5-4bb2-8ee8-0d7b52f5d08b`

## Steps that need attention

None. Every step of the investigation ran cleanly.

## Where the fault is in the application

_green = fine · amber = worth a look · red = the fault · grey dashed = not visited_

```mermaid
flowchart LR
    cicd["CI/CD pipeline<br/>build, tests, deploy<br/>not checked"]:::skipped
    config["Configuration<br/>env vars, secrets, probes<br/>not checked"]:::skipped
    kubernetes["Kubernetes<br/>pods, memory limits, restarts<br/>not checked"]:::skipped
    service["Service<br/>latency, error rate, logs<br/>application_error (0.80)"]:::warning
    traffic["Traffic<br/>user load<br/>not checked"]:::skipped
    dependency["Dependencies<br/>database, downstream services<br/>ROOT CAUSE: dependency_issue (0.60)"]:::error
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
    load_evidence["load_evidence<br/>collect CI/CD, Kubernetes, observability evidence<br/>Load evidence (15 items)"]:::ok
    spawn_agent["spawn_agent<br/>create a specialist if none covers a problem<br/>spawned: cache_analyzer"]:::ok
    route["route<br/>choose the next specialist<br/>visited 3 times"]:::ok
    invoke_agent["invoke_agent<br/>run that specialist<br/>ran: cache_analyzer, dependency_analyzer, observability_analyzer"]:::ok
    evaluate["evaluate<br/>is confidence high enough?<br/>visited 3 times"]:::ok
    critique["critique<br/>critic reviews the conclusion<br/>Critic 1: confirmed (0.80)"]:::ok
    generate_rca["generate_rca<br/>write root cause + remediation<br/>Root cause: dependency_issue (0.78)"]:::ok
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
| 1 | ✔ | `normalize` | Start investigation | Incident incident-008: Checkout latency and errors: Redis cache full and evicting keys<br>Decisions made by: rules |
| 2 | ✔ | `pre_filter` | Keyword pre-filter | First guess: traffic_incident<br>Wants to know about: observability_metrics, cache_health |
| 3 | ✔ | `load_evidence` | Load evidence (15 items) | Sources: kubernetes_fixture, observability_fixture |
| 4 | ✔ | `spawn_agent` | Spawned cache_analyzer | No available specialist covers this, so cache_analyzer was created: Cache: cache servers that are full, evicting keys, or no longer absorbing load<br>Because: The incident mentions cache and no specialist covers it: "Checkout latency and errors: Redis cache full and evicting keys" |
| 5 | ✔ | `route` | Route #1 -> cache_analyzer | Spawned for this incident (Cache: cache servers that are full, evicting keys, or no longer absorbing load); nothing else covers it, so it runs first |
| 6 | ✔ | `invoke_agent` | cache_analyzer: dependency_issue (0.75) | Cache: Log: Redis maxmemory reached: evicting keys (allkeys-lru), used_memory 2.00GB of 2.00GB; Log: Redis evicted_keys=1.2M in the last 10 minutes; cache hit ratio 18%; Log: GET /cart 500: cache lookup failed, falling back to database<br>Evidence cited: 3, of which real: 3 |
| 7 | ✔ | `evaluate` | Confidence 0.68 / 0.75 (not enough yet) | Per agent: cache_analyzer 0.78 |
| 8 | ✔ | `route` | Route #2 -> dependency_analyzer | Recent finding suggests dependency_issue; routing to dependency_analyzer |
| 9 | ✔ | `invoke_agent` | dependency_analyzer: dependency_issue (0.60) | Failing dependencies - databases, caches, downstream services, libraries: Log: GET /cart 500: cache lookup failed, falling back to database; Log: cache miss ratio 82% for key prefix session:*, every request now reads the database<br>Evidence cited: 2, of which real: 2 |
| 10 | ✔ | `evaluate` | Confidence 0.73 / 0.75 (not enough yet) | Per agent: cache_analyzer 0.78, dependency_analyzer 0.64 |
| 11 | ✔ | `route` | Route #3 -> observability_analyzer | Hypothesis 'traffic_incident' maps to observability_analyzer |
| 12 | ✔ | `invoke_agent` | observability_analyzer: application_error (0.80) | The application is erroring (14% errors, 0 stack traces)<br>Evidence cited: 1, of which real: 1 |
| 13 | ✔ | `evaluate` | Confidence 0.78 / 0.75 (enough) | Per agent: cache_analyzer 0.78, dependency_analyzer 0.64, observability_analyzer 0.74 |
| 14 | ✔ | `critique` | Critic #1: confirmed (0.80) |  |
| 15 | ✔ | `generate_rca` | Root cause: dependency_issue (0.78) | Agents used: cache_analyzer -> dependency_analyzer -> observability_analyzer |
| 16 | ✔ | `persist` | Finished: completed |  |
