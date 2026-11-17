# Flow report: shoplite-S2

**ShopLite pods OOMKilled repeatedly — memory limit 128Mi exceeded**

- Result: Investigation FAILED at node 'invoke_agent'.
- Decisions made by: `rules+fault:agent_crash`
- Investigation id: `27340da4-303a-48d8-a5f7-59577c79bb8c`
- Injected fault (demo): `agent_crash`

## Steps that need attention

- ✖ **invoke_agent** - invoke_agent (kubernetes_analyzer) FAILED
  - RuntimeError: LLM provider timed out after 60s (injected fault: agent_crash)

## Where the fault is in the application

_green = fine · amber = worth a look · red = the fault · grey dashed = not visited_

```mermaid
flowchart LR
    cicd["CI/CD pipeline<br/>build, tests, deploy<br/>not checked"]:::skipped
    config["Configuration<br/>env vars, secrets, probes<br/>not checked"]:::skipped
    kubernetes["Kubernetes<br/>pods, memory limits, restarts<br/>not checked"]:::skipped
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
    load_evidence["load_evidence<br/>collect CI/CD, Kubernetes, observability evidence<br/>Load evidence (22 items)"]:::ok
    spawn_agent["spawn_agent<br/>create a specialist if none covers a problem<br/>ran, nothing to do"]:::ok
    route["route<br/>choose the next specialist<br/>Route 1 -> kubernetes_analyzer"]:::ok
    invoke_agent["invoke_agent<br/>run that specialist<br/>invoke_agent (kubernetes_analyzer) FAILED"]:::error
    evaluate["evaluate<br/>is confidence high enough?<br/>not reached"]:::skipped
    critique["critique<br/>critic reviews the conclusion<br/>not reached"]:::skipped
    generate_rca["generate_rca<br/>write root cause + remediation<br/>not reached"]:::skipped
    persist["persist<br/>finish<br/>not reached"]:::skipped
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
    linkStyle 0,1,2,3,4 stroke-width:3px
    classDef ok fill:#d1f2d9,stroke:#1a7f37,color:#0b2e13
    classDef warning fill:#fff1c2,stroke:#9a6700,color:#3b2a00
    classDef error fill:#ffd7d5,stroke:#cf222e,color:#5c0a0f,stroke-width:3px
    classDef skipped fill:#f3f3f3,stroke:#999999,color:#666666,stroke-dasharray:4 3
```

## Step by step

| # | | Node | What happened | Details |
|---|---|---|---|---|
| 1 | ✔ | `normalize` | Start investigation | Incident shoplite-S2: ShopLite pods OOMKilled repeatedly — memory limit 128Mi exceeded<br>Decisions made by: rules+fault:agent_crash<br>Injected fault for this demo run: agent_crash |
| 2 | ✔ | `pre_filter` | Keyword pre-filter | First guess: kubernetes_oom<br>Wants to know about: deployment_details, pod_memory_status, pod_restart_pattern |
| 3 | ✔ | `load_evidence` | Load evidence (22 items) | Sources: cicd_fixture, kubernetes_fixture, observability_fixture |
| 4 | ✔ | `route` | Route #1 -> kubernetes_analyzer | Hypothesis 'kubernetes_oom' maps to kubernetes_analyzer |
| 5 | ✖ | `invoke_agent` | invoke_agent (kubernetes_analyzer) FAILED | RuntimeError: LLM provider timed out after 60s (injected fault: agent_crash) |
