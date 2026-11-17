# Flow report: shoplite-S1

**ShopLite CI pipeline failing — tests broken after commit**

- Result: Root cause: deployment_induced_failure (confidence 0.81, status completed).
- Decisions made by: `rules`
- Investigation id: `fbdbace3-3e93-4166-9227-ce940ef8b2e6`

## Steps that need attention

None. Every step of the investigation ran cleanly.

## Where the fault is in the application

_green = fine · amber = worth a look · red = the fault · grey dashed = not visited_

```mermaid
flowchart LR
    cicd["CI/CD pipeline<br/>build, tests, deploy<br/>ROOT CAUSE: deployment_induced_failure (0.90)"]:::error
    config["Configuration<br/>env vars, secrets, probes<br/>configuration_error (0.60)"]:::warning
    kubernetes["Kubernetes<br/>pods, memory limits, restarts<br/>checked, nothing found"]:::ok
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
    load_evidence["load_evidence<br/>collect CI/CD, Kubernetes, observability evidence<br/>Load evidence (7 items)"]:::ok
    spawn_agent["spawn_agent<br/>create a specialist if none covers a problem<br/>ran, nothing to do"]:::ok
    route["route<br/>choose the next specialist<br/>visited 3 times"]:::ok
    invoke_agent["invoke_agent<br/>run that specialist<br/>ran: cicd_analyzer, kubernetes_analyzer, config_analyzer"]:::ok
    evaluate["evaluate<br/>is confidence high enough?<br/>visited 3 times"]:::ok
    critique["critique<br/>critic reviews the conclusion<br/>visited 3 times"]:::ok
    generate_rca["generate_rca<br/>write root cause + remediation<br/>Root cause: deployment_induced_failure (0.81)"]:::ok
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
| 1 | ✔ | `normalize` | Start investigation | Incident shoplite-S1: ShopLite CI pipeline failing — tests broken after commit<br>Decisions made by: rules |
| 2 | ✔ | `pre_filter` | Keyword pre-filter | First guess: unknown |
| 3 | ✔ | `load_evidence` | Load evidence (7 items) | Sources: cicd_fixture, observability_fixture |
| 4 | ✔ | `route` | Route #1 -> cicd_analyzer | Default selection: cicd_analyzer |
| 5 | ✔ | `invoke_agent` | cicd_analyzer: deployment_induced_failure (0.90) | The deployment failed; the incident starts right after it: Deployment shoplite-deploy-S1 at 2024-06-01T09:00:00Z<br>Evidence cited: 3, of which real: 2 |
| 6 | ✔ | `evaluate` | Confidence 0.81 / 0.75 (enough) | Per agent: cicd_analyzer 0.81 |
| 7 | ✔ | `critique` | Critic #1: challenged (0.60) | The 'deployment_induced_failure' conclusion rests on a single layer (cicd_analyzer); nothing independent corroborates it.<br>Sent back to the router; suggested agent: kubernetes_analyzer |
| 8 | ✔ | `route` | Route #2 -> kubernetes_analyzer | Critic challenged the conclusion and suggested kubernetes_analyzer |
| 9 | ✔ | `invoke_agent` | kubernetes_analyzer: unknown (0.10) | No Kubernetes evidence found for this incident<br>Evidence cited: 0, of which real: 0 |
| 10 | ✔ | `evaluate` | Confidence 0.81 / 0.75 (enough) | Per agent: cicd_analyzer 0.81 |
| 11 | ✔ | `critique` | Critic #2: challenged (0.60) | The 'deployment_induced_failure' conclusion rests on a single layer (cicd_analyzer); nothing independent corroborates it.<br>Sent back to the router; suggested agent: config_analyzer |
| 12 | ✔ | `route` | Route #3 -> config_analyzer | Critic challenged the conclusion and suggested config_analyzer |
| 13 | ✔ | `invoke_agent` | config_analyzer: configuration_error (0.60) | Configuration changes - env vars, secrets, probes, ports: Config change: FLAKY_TESTS = true; Log: FAILED tests/test_app.py::test_flaky_import_error - ModuleNotFoundError: No module named 'app.nonexistent_module'<br>Evidence cited: 2, of which real: 2 |
| 14 | ✔ | `evaluate` | Confidence 0.81 / 0.75 (enough) | Per agent: cicd_analyzer 0.81, config_analyzer 0.67 |
| 15 | ✔ | `critique` | Critic #3: confirmed (0.90) |  |
| 16 | ✔ | `generate_rca` | Root cause: deployment_induced_failure (0.81) | Agents used: cicd_analyzer -> kubernetes_analyzer -> config_analyzer |
| 17 | ✔ | `persist` | Finished: completed |  |
