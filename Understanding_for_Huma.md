# Understanding AgentOps — Backend Deep Dive

> Written for Huma. Assumes zero prior knowledge of the project. Everything is explained from scratch.

---

## Table of Contents

1. [What is AgentOps? (The Big Picture)](#1-what-is-agentops-the-big-picture)
2. [How the System Works — One Sentence Each Layer](#2-how-the-system-works)
3. [Project Folder Structure](#3-project-folder-structure)
4. [Backend File-by-File Explainer](#4-backend-file-by-file-explainer)
   - [4.1 Entry Point](#41-entry-point)
   - [4.2 Configuration](#42-configuration)
   - [4.3 Real-time Events](#43-real-time-events)
   - [4.4 API Layer](#44-api-layer)
   - [4.5 Models](#45-models)
   - [4.6 Orchestrator](#46-orchestrator)
   - [4.7 Agents](#47-agents)
   - [4.8 LLM Layer](#48-llm-layer)
   - [4.9 Runtime](#49-runtime)
   - [4.10 Services](#410-services)
   - [4.11 Tools / Data Access](#411-tools--data-access)
   - [4.12 Data Sources](#412-data-sources)
5. [ASCII Flow Diagram — Full Investigation Pipeline](#5-ascii-flow-diagram--full-investigation-pipeline)
6. [Key Concepts Glossary](#6-key-concepts-glossary)

---

## 1. What is AgentOps? (The Big Picture)

Imagine your company's website goes down at 3 AM. Something broke in production. Normally a human engineer would:

1. Look at deployment logs — "did anyone push code recently?"
2. Check Kubernetes — "did a container crash?"
3. Check metrics — "is the error rate spiking?"
4. Put it all together and say: "It looks like the memory limit was lowered in the last deploy — that killed the pod."

**AgentOps automates all of that.** It is a backend system that, when given an incident description:
- Automatically collects evidence from CI/CD (GitHub Actions), Kubernetes, and observability tools
- Sends that evidence to specialist AI "agents" that analyze it
- Decides which agent to use next based on what gaps remain
- Builds confidence scores as evidence accumulates
- Stops when it is confident enough about the root cause
- Writes a Root Cause Analysis (RCA) report and a remediation plan

The backend is **Python 3.11 + FastAPI**. The brain of the system is **LangGraph** — a framework for defining AI workflows as graphs (think: flowcharts where each box is a Python async function).

---

## 2. How the System Works

| Layer | One-Line Summary |
|-------|-----------------|
| **API** | Receives an incident over HTTP, returns investigation status |
| **Service** | Coordinates the full investigation lifecycle |
| **Orchestrator (Graph)** | Runs the investigation as a step-by-step graph |
| **Router** | Decides which specialist agent to call next |
| **Agents** | Analyze evidence and return findings with confidence scores |
| **LLM** | Powers the agents with AI reasoning (or mock for dev/testing) |
| **Tools / Data Access** | Loads evidence from GitHub, fixture files, Kubernetes data |
| **Models** | Defines all data shapes (Incident, Evidence, Finding, RCA...) |
| **MongoDB** | Stores everything persistently |
| **WebSocket** | Streams live progress to the browser dashboard |

---

## 3. Project Folder Structure

```
AgentOps/
├── backend/                  ← ALL PYTHON CODE LIVES HERE
│   ├── main.py               ← FastAPI app entry point
│   ├── config.py             ← All settings (.env reading)
│   ├── events.py             ← WebSocket broadcast functions
│   ├── requirements.txt      ← Python package list
│   │
│   ├── api/                  ← HTTP endpoints & WebSocket handler
│   │   ├── routes.py         ← REST API (POST /incidents, GET /investigations/...)
│   │   └── websocket.py      ← WebSocket connection handler
│   │
│   ├── models/               ← Data shapes (Pydantic)
│   │   ├── __init__.py       ← All Pydantic models (Incident, Evidence, etc.)
│   │   └── mongodb.py        ← MongoDB Document classes (Beanie ODM)
│   │
│   ├── orchestrator/         ← The investigation "brain"
│   │   ├── graph.py          ← LangGraph workflow (the main pipeline)
│   │   ├── router.py         ← Deterministic agent-selection fallback
│   │   ├── state.py          ← MongoDB state manager (CRUD operations)
│   │   ├── confidence.py     ← Confidence math + RCA/remediation synthesis
│   │   └── __init__.py       ← Exports build_investigation_graph
│   │
│   ├── agents/               ← Specialist investigators
│   │   ├── cicd/agent.py         ← CI/CD evidence analyzer (deterministic)
│   │   ├── kubernetes/agent.py   ← K8s evidence analyzer (deterministic)
│   │   ├── observability/agent.py ← Metrics/logs analyzer (deterministic)
│   │   └── markdown/             ← LLM prompt definitions (loaded at runtime)
│   │       ├── router.md
│   │       ├── cicd_analyzer.md
│   │       ├── kubernetes_analyzer.md
│   │       ├── observability_analyzer.md
│   │       ├── rca_synthesizer.md
│   │       └── remediation_planner.md
│   │
│   ├── llm/                  ← AI model abstraction
│   │   ├── base.py           ← Abstract interface all LLMs must implement
│   │   ├── mock.py           ← Fake LLM for development/testing
│   │   ├── nemotron.py       ← Real Nemotron LLM (NVIDIA API)
│   │   ├── schemas.py        ← Pydantic models for structured LLM output
│   │   └── __init__.py       ← Factory: returns mock or real LLM based on config
│   │
│   ├── runtime/              ← Agent execution engine
│   │   ├── agent_runner.py   ← Builds prompts, calls LLM, parses output
│   │   ├── agent_loader.py   ← Reads .md files from agents/markdown/
│   │   └── __init__.py       ← Exports get_agent_runner
│   │
│   ├── services/             ← Business logic
│   │   ├── investigation_service.py  ← Coordinates the full pipeline
│   │   ├── mongodb.py                ← Connects Beanie to MongoDB on startup
│   │   └── github_monitor.py         ← Background poller: auto-creates incidents from GitHub failures
│   │
│   ├── tools/                ← Evidence loading utilities
│   │   └── data_access.py    ← Loads evidence from fixture files or GitHub API
│   │
│   └── data_sources/         ← External API clients
│       └── github_actions/   ← GitHub REST API client + data adapter
│
├── data/                     ← Fixture / test data (JSON files)
│   ├── incidents/            ← Sample incident descriptions
│   ├── cicd/                 ← Sample CI/CD data
│   ├── kubernetes/           ← Sample K8s pod/resource data
│   ├── observability/        ← Sample metrics/logs
│   └── ground_truth/         ← Expected RCA answers (for evaluation)
│
├── tests/                    ← Unit and integration tests
├── evaluation/               ← Evaluation framework (baseline comparison)
├── docker/                   ← Dockerfiles + nginx config
├── docker-compose.yml        ← Local dev stack (backend + frontend + MongoDB)
├── .env.example              ← Environment variables template
└── frontend/                 ← React dashboard (not covered here)
```

---

## 4. Backend File-by-File Explainer

---

### 4.1 Entry Point

---

#### `backend/main.py`

**What it is:** The very first file Python runs. Creates the FastAPI web server and wires everything together.

**What it does step by step:**

1. **Configures structured logging** using `structlog` — all log output is JSON, making it machine-readable and easy to query.

2. **Defines `lifespan(app)`** — a special async function FastAPI calls on startup and shutdown:
   - **On startup:** connects to MongoDB (`await mongodb.connect()`), starts the GitHub Actions background monitor
   - **On shutdown:** stops the monitor, closes the MongoDB connection

3. **Creates the FastAPI app** with a title, description, version, and CORS middleware (Cross-Origin Resource Sharing — this is what allows the React frontend on `localhost:3000` to talk to the backend on `localhost:8000`).

4. **Registers two API routers:**
   - `router` → handles `/api/incidents/...`
   - `investigation_router` → handles `/api/investigations/...`

5. **Adds health endpoints:**
   - `GET /` — returns service name and version
   - `GET /health` — returns `{"status": "healthy"}` — used by Docker healthchecks

**Key imports:**
```
FastAPI, CORSMiddleware      ← web server framework
settings                     ← all environment config
mongodb                      ← database connection manager
start_github_monitor         ← background CI/CD watcher
router, investigation_router ← API endpoint definitions
```

---

#### `backend/requirements.txt`

**What it is:** The list of all Python packages this project depends on.

Key packages and why they're there:

| Package | Purpose |
|---------|---------|
| `fastapi`, `uvicorn` | Web server |
| `pydantic`, `pydantic-settings` | Data validation and settings management |
| `motor`, `beanie` | Async MongoDB driver + ODM |
| `langgraph` | Graph-based AI workflow engine |
| `openai` | SDK used to call Nemotron LLM (NVIDIA's API is OpenAI-compatible) |
| `structlog` | Structured JSON logging |
| `httpx`, `aiohttp` | Async HTTP clients (for GitHub API calls) |

---

### 4.2 Configuration

---

#### `backend/config.py`

**What it is:** A single place where ALL configuration lives. Instead of calling `os.environ.get(...)` scattered throughout the codebase, this file reads the `.env` file once and exposes a typed `settings` object.

**How it works:** Uses Pydantic's `BaseSettings`. Every field has a default value. If a matching environment variable exists in `.env` (case-insensitive), it overrides the default.

**Key settings grouped by purpose:**

*App basics:*
| Setting | Default | Meaning |
|---------|---------|---------|
| `app_env` | `development` | Environment label |
| `debug` | `True` | Debug mode on/off |
| `backend_host` | `0.0.0.0` | Which network interface to bind |
| `backend_port` | `8000` | Port to listen on |

*Database:*
| Setting | Default | Meaning |
|---------|---------|---------|
| `mongodb_uri` | `mongodb://localhost:27017` | Where MongoDB is running |
| `mongodb_database` | `agentops` | Which database to use |

*LLM:*
| Setting | Default | Meaning |
|---------|---------|---------|
| `llm_provider` | `mock` | `mock` = fake LLM, `nemotron` = real NVIDIA AI |
| `nemotron_api_key` | None | NVIDIA API key (required for real LLM) |
| `nemotron_api_url` | None | NVIDIA API endpoint URL |
| `llm_trace_enabled` | `False` | If True, saves every LLM call to a file |
| `llm_trace_path` | `logs/llm_traces.jsonl` | Where LLM traces are written |

*Investigation behavior:*
| Setting | Default | Meaning |
|---------|---------|---------|
| `max_iterations` | `5` | Max investigation rounds before giving up |
| `confidence_threshold` | `0.75` | Stop investigating when confidence ≥ 75% |

*GitHub:*
| Setting | Default | Meaning |
|---------|---------|---------|
| `github_token` | None | GitHub personal access token |
| `github_owner` | None | GitHub org/user owning the repo |
| `github_repo` | None | GitHub repository name to monitor |
| `github_poll_interval_seconds` | `60` | How often to check GitHub for new failures |
| `github_time_window_hours` | `24` | How far back to look for relevant runs |

**Usage across the codebase:**
```python
from backend.config import settings
settings.mongodb_uri       # read any value
settings.confidence_threshold  # 0.75
```

---

### 4.3 Real-time Events

---

#### `backend/events.py`

**What it is:** The pub/sub (publish-subscribe) system for real-time updates. While the backend investigates an incident, it continuously "broadcasts" progress messages to the frontend dashboard via WebSocket.

**Component 1 — `ConnectionManager` class:**

Keeps a dictionary: `investigation_id → set of WebSocket connections`

- `connect(investigation_id, websocket)` — accepts and registers a new browser tab's connection
- `disconnect(investigation_id, websocket)` — removes a connection when the browser closes
- `broadcast(investigation_id, message)` — sends a JSON message to ALL browsers currently watching that investigation
- Uses `asyncio.Lock` to safely handle multiple concurrent connections

**Component 2 — Broadcast helper functions:**

These are thin wrappers that format a message and call `connection_manager.broadcast()`:

| Function | When called | What the browser receives |
|----------|------------|--------------------------|
| `broadcast_status_change` | When status changes | `"running"` → `"completed"` |
| `broadcast_progress` | After each graph step | `{iteration: 2, max: 5, confidence: 0.92}` |
| `broadcast_routing_decision` | After router picks an agent | `{selected_agent: "kubernetes", reasoning: "..."}` |
| `broadcast_agent_thinking` | Before/after an agent runs | `{agent_type: "cicd", status: "started"}` |
| `broadcast_agent_finding` | When agent produces a result | `{finding: "Pod OOMKilled", confidence: 0.92}` |

**Important design detail:** This file avoids importing from `api/websocket.py` to prevent circular imports. It uses a lazy import pattern (`from fastapi import WebSocket` inside the function body, not at the top of the file).

**Global instance:**
```python
connection_manager = ConnectionManager()  # one instance for the whole app
```

---

### 4.4 API Layer

---

#### `backend/api/routes.py`

**What it is:** Defines every HTTP URL the system exposes. Split into two FastAPI `APIRouter` objects.

**Router 1 — `/api/incidents`:**

| Method + URL | What it does |
|---|---|
| `POST /api/incidents` | Accepts an `Incident` JSON body, starts investigation, returns `investigation_id` |
| `GET /api/incidents` | Returns a lightweight list of all investigations (status, confidence, agents used, etc.) |
| `GET /api/incidents/{incident_id}` | Returns the investigation status for one specific incident |

**Router 2 — `/api/investigations`:**

| Method + URL | What it does |
|---|---|
| `GET /api/investigations/{id}` | Full investigation detail — complete `InvestigationState` |
| `DELETE /api/investigations/{id}` | Deletes an investigation from MongoDB |
| `GET /api/investigations/{id}/timeline` | All findings, routing decisions, confidence updates sorted by timestamp |
| `GET /api/investigations/{id}/evidence` | All collected `Evidence` objects |
| `GET /api/investigations/{id}/root-cause` | The Root Cause Analysis result |
| `GET /api/investigations/{id}/remediation` | The fix plan |
| `WebSocket /api/investigations/{id}/ws` | Opens a persistent connection to receive live updates |

**How `POST /api/incidents` flows internally:**
```
1. Deserialize request body → Incident object
2. Call investigation_service.start_investigation(incident)
   ↳ This runs the FULL graph pipeline synchronously
3. Return InvestigationResponse { investigation_id, status, message }
```

---

#### `backend/api/websocket.py`

**What it is:** The handler for WebSocket connections — when a browser connects to watch a live investigation.

**What it does:**
1. Calls `connection_manager.connect(investigation_id, websocket)` to register
2. Immediately sends the current investigation state as `{"type": "initial_state", ...}` so the browser shows the right data even if it connects after the investigation started
3. Enters a loop listening for messages from the browser:
   - `{"type": "ping"}` → replies `{"type": "pong"}` (keep-alive)
   - `WebSocketDisconnect` exception → breaks the loop
4. On any disconnect: calls `connection_manager.disconnect()` to clean up

---

### 4.5 Models

---

#### `backend/models/__init__.py`

**What it is:** All the data structures used across the entire system. Every piece of data has a strict "shape" defined here using Pydantic — which means if you try to create an object with wrong types, you get an error immediately rather than a hard-to-debug bug later.

**Enums (the allowed values for certain fields):**

| Enum | Values |
|------|--------|
| `IncidentSeverity` | `low`, `medium`, `high`, `critical` |
| `IncidentStatus` | `open`, `investigating`, `resolved`, `closed` |
| `AgentType` | `cicd`, `kubernetes`, `observability` |
| `InvestigationStatus` | `pending`, `running`, `completed`, `failed`, `max_iterations_reached`, `insufficient_evidence` |
| `EvidenceType` | `deployment`, `code_change`, `config_change`, `pod_exit_code`, `pod_restart_count`, `pod_event`, `resource_usage`, `resource_limit`, `latency`, `error_rate`, `log`, `stack_trace`, `trace`, `span_duration`, `error_status`, `job_failure` |
| `HypothesisType` | `deployment_induced_failure`, `kubernetes_oom`, `application_error`, `configuration_error`, `dependency_issue`, `traffic_incident`, `multi_layer_failure`, `unknown` |

**Core models explained:**

---

**`Incident`** — The production problem that triggered everything
```
incident_id    → auto-generated UUID
title          → short name, e.g. "Payment service OOMKilled"
description    → detailed description of what went wrong
severity       → low / medium / high / critical
source         → "github_actions" or "manual"
service_name   → e.g. "payment-service"
namespace      → Kubernetes namespace
started_at     → when the incident began
metadata       → free-form extra info dict
tags           → list of string labels
```

---

**`Evidence`** — A single verifiable fact collected during investigation
```
evidence_id    → auto-generated UUID
agent_type     → which domain this belongs to (cicd / kubernetes / observability)
evidence_type  → EvidenceType enum
description    → human-readable summary
raw_data       → the actual data dict, e.g. {"exit_code": 137, "pod": "payment-abc"}
confidence     → 0.0–1.0, how reliable this evidence is
source         → "github_actions", "kubernetes_fixture", etc.
```

---

**`AgentFinding`** — What a specialist agent concluded after analyzing evidence
```
finding_id     → auto-generated UUID
agent_type     → which agent produced this
hypothesis     → HypothesisType — the agent's best guess at root cause
finding        → human-readable conclusion, e.g. "Pod was OOMKilled due to memory exhaustion"
evidence       → list of evidence_id strings this finding is grounded in
confidence     → 0.0–1.0, how sure the agent is
reasoning      → step-by-step reasoning text
iteration      → which investigation round produced this
```

---

**`RoutingDecision`** — A log entry of which agent was chosen and why
```
iteration       → which round this decision was made in
evidence_gaps   → what we still don't know at this point
selected_agent  → AgentType that was chosen
reasoning       → why this agent was chosen (LLM or deterministic logic)
agents_invoked  → agents already used before this decision
available_agents → agents still available to call
```

---

**`ConfidenceEntry`** — A snapshot of confidence scores at a given iteration
```
iteration         → round number
agent_confidences → per-agent scores, e.g. {"cicd": 0.85, "kubernetes": 0.92}
overall_confidence → combined score (currently: max of all agents)
threshold         → the target (0.75 by default)
is_sufficient     → True if overall >= threshold
```

---

**`RootCauseAnalysis`** — The final "why did this happen" report
```
root_cause          → plain-English explanation with "What happened" and "Why it happened"
root_cause_type     → HypothesisType of the primary cause
contributing_factors → list of supporting factors
evidence            → evidence references
agents_consulted    → which agents participated
overall_confidence  → final confidence score
investigation_timeline → ordered list of all findings + routing decisions
```

---

**`RemediationRecommendation`** — The fix plan
```
recommendation  → high-level summary of the fix
steps           → ["Step 1: Revert deployment", "Step 2: Monitor memory", ...]
priority        → high / medium / low
estimated_effort → low / medium / high
risk_level      → low / medium / high
status          → pending / in_progress / done
```

---

**`InvestigationState`** — The master object that holds EVERYTHING about one investigation
```
investigation_id    → auto-generated UUID
incident            → the Incident object
current_hypothesis  → best current guess (HypothesisType)
evidence            → list of ALL Evidence collected so far
agent_findings      → list of ALL AgentFindings so far
agents_invoked      → which agents have run
confidence_scores   → per-agent confidence dict
overall_confidence  → current combined score
iteration_count     → how many rounds have run
max_iterations      → when to give up (from settings, default 5)
evidence_gaps       → what we still need to find
investigation_status → InvestigationStatus enum
root_cause          → RootCauseAnalysis (once generated)
remediation         → RemediationRecommendation (once generated)
routing_decisions   → list of RoutingDecisions
confidence_history  → list of ConfidenceEntries
created_at, updated_at, completed_at
```

---

#### `backend/models/mongodb.py`

**What it is:** The same data structures as above, but defined as MongoDB "Documents" using Beanie (a MongoDB ODM — Object-Document Mapper). Beanie knows how to serialize Python objects to MongoDB and back.

**How it differs from `models/__init__.py`:**
- Each class inherits from `beanie.Document` instead of `pydantic.BaseModel`
- Each has a `class Settings` with `name = "collection_name"` that sets the MongoDB collection

**MongoDB collections created:**

| Beanie Document class | MongoDB Collection | What's stored |
|---|---|---|
| `IncidentDoc` | `incidents` | Incident data |
| `InvestigationDoc` | `investigations` | Investigation metadata + lists of IDs |
| `EvidenceDoc` | `evidence` | Individual evidence items |
| `AgentFindingDoc` | `agent_findings` | Agent conclusions |
| `RoutingDecisionDoc` | `routing_decisions` | Router choices |
| `ConfidenceEntryDoc` | `confidence_history` | Confidence snapshots |
| `RootCauseAnalysisDoc` | `root_cause_analyses` | Final RCA reports |
| `RemediationDoc` | `remediations` | Fix plans |
| `ProcessedRunDoc` | `processed_runs` | Which GitHub workflow run IDs were already processed (prevents duplicate incidents) |

**Key design note about `InvestigationDoc`:** It does NOT embed Evidence, Findings, etc. directly inside itself. Instead it stores **lists of IDs** (`evidence_ids`, `finding_ids`, etc.) and each related item lives in its own collection. This is normalized design — better for querying individual items.

---

### 4.6 Orchestrator

The orchestrator is the investigation brain. It defines what happens and in what order.

---

#### `backend/orchestrator/graph.py`

**What it is:** The investigation pipeline defined as a LangGraph `StateGraph`. Each node is one async Python function. Edges connect them in sequence, and conditional edges branch based on runtime decisions.

**The graph nodes (each is one step of investigation):**

| Node | What it does |
|------|-------------|
| `normalize` | Sets `investigation_status = RUNNING` |
| `pre_filter` | Scans incident title/description for keywords → sets initial hypothesis + evidence gaps |
| `load_evidence` | Fetches CI/CD, K8s, and Observability evidence from fixtures/GitHub |
| `route` | Asks the Router (LLM or fallback) which specialist agent to invoke next |
| `invoke_cicd` | Runs the CI/CD analysis agent |
| `invoke_kubernetes` | Runs the Kubernetes analysis agent |
| `invoke_observability` | Runs the Observability analysis agent |
| `evaluate` | Calculates confidence; decides if we're done or should loop |
| `generate_rca` | Synthesizes Root Cause Analysis + Remediation |
| `persist` | Final save step (actual MongoDB write happens in the service) |

**The edges:**
```
START → normalize → pre_filter → load_evidence → route
                                                   ↓ (conditional, based on selected agent)
                               invoke_cicd / invoke_kubernetes / invoke_observability
                                                   ↓
                                               evaluate
                                                   ↓ (conditional)
                              route (loop back) OR generate_rca
                                                   ↓
                                               persist → END
```

**Key node details:**

`rule_based_pre_filter` — keyword scan on incident title + description:
- "deployment", "deploy", "rollout" → `hypothesis = DEPLOYMENT_INDUCED_FAILURE`, `gaps = ["deployment_details"]`
- "oom", "memory", "exit code 137", "crashloop" → `hypothesis = KUBERNETES_OOM`, `gaps = ["pod_memory_status"]`
- "latency", "slow", "timeout", "5xx", "error rate" → `hypothesis = TRAFFIC_INCIDENT`, `gaps = ["observability_metrics"]`
- "config", "environment variable" → `hypothesis = CONFIGURATION_ERROR`, `gaps = ["configuration_changes"]`

`adaptive_router` — the routing node:
1. If `iteration_count >= max_iterations` → skip to `generate_rca`
2. Calls `AgentRunner.run_router_agent()` which uses the `router.md` LLM prompt
3. If LLM returns an unavailable agent → falls back to `router.py`'s deterministic logic
4. Records the decision as a `RoutingDecision`
5. Increments `iteration_count`

`_invoke_analysis_agent` — shared logic for all three agent nodes:
1. Broadcasts `"started"` via WebSocket
2. Calls `AgentRunner.run_analysis_agent()` → LLM with the agent's `.md` prompt
3. If LLM fails or returns bad JSON → falls back to deterministic Python agent
4. Appends `AgentFinding` to investigation
5. Updates `confidence_scores[agent_type]`
6. Resolves any `evidence_gaps` that are now covered
7. Broadcasts `"completed"` via WebSocket

`evaluate_evidence`:
1. Calls `calculate_overall_confidence()` → returns `max(per-agent scores)`
2. Appends a `ConfidenceEntry` snapshot
3. If `overall_confidence >= threshold (0.75)` → move to `generate_rca`
4. If `iteration_count >= max_iterations` → move to `generate_rca`
5. Otherwise → loop back to `route`

`generate_rca`:
1. Calls `AgentRunner.run_rca_agent()` — LLM with `rca_synthesizer.md` prompt
2. LLM failure → falls back to `confidence.py`'s `synthesize_rca()`
3. Calls `AgentRunner.run_remediation_agent()` — LLM with `remediation_planner.md`
4. LLM failure → falls back to `confidence.py`'s `generate_remediation()`
5. Stores both on `investigation.root_cause` and `investigation.remediation`

---

#### `backend/orchestrator/router.py`

**What it is:** The deterministic fallback router. When the LLM-based router in `graph.py` fails or returns bad output, this pure-Python logic takes over.

**The gap → agent mapping:**
```python
gap_agent_map = {
    "deployment_details"    → AgentType.CICD,
    "configuration_changes" → AgentType.CICD,
    "pod_memory_status"     → AgentType.KUBERNETES,
    "pod_restart_pattern"   → AgentType.KUBERNETES,
    "resource_pressure"     → AgentType.KUBERNETES,
    "observability_metrics" → AgentType.OBSERVABILITY,
    "error_patterns"        → AgentType.OBSERVABILITY,
    "trace_analysis"        → AgentType.OBSERVABILITY,
}
```

**Selection priority order:**
1. Check `evidence_gaps` → find the agent that covers the highest-priority gap
2. Check `current_hypothesis` → override if hypothesis strongly implies a domain (e.g. `KUBERNETES_OOM` → call KUBERNETES agent)
3. Check recent `agent_findings` → if a finding hints at a domain, follow it
4. Fallback → first available agent not yet invoked

---

#### `backend/orchestrator/state.py`

**What it is:** The MongoDB data access layer. All read/write operations for `InvestigationState` go through `MongoStateManager`.

**Why it exists:** `InvestigationState` is a complex Pydantic object with nested lists of Evidence, Findings, Decisions, etc. MongoDB stores each type in its own collection. The state manager handles converting between these two representations.

**Key methods:**

| Method | What it does |
|--------|-------------|
| `create_state(incident, max_iterations, evidence)` | Creates `InvestigationState`, saves `IncidentDoc` + `InvestigationDoc` + all `EvidenceDoc`s to MongoDB |
| `get_state(investigation_id)` | Reads `InvestigationDoc`, then loads all related Evidence, Findings, Decisions, RCA, Remediation from their collections and assembles a full `InvestigationState` |
| `update_state(state)` | Saves any NEW Evidence/Findings/Decisions (only inserts, never double-inserts) |
| `delete_state(investigation_id)` | Deletes the investigation + all related documents from all collections |
| `list_states(status)` | Lists all investigations with full related data loaded |
| `list_states_lite(status)` | Lists all investigations **without** loading Evidence/Findings (much faster for dashboards that just need status + metadata) |

**Conversion helpers:** Each data type has both a `_to_doc()` (Pydantic → MongoDB Document) and a `_doc_to_...()` (MongoDB Document → Pydantic) method.

**Global singleton at bottom of file:**
```python
mongo_state_manager = MongoStateManager()
state_manager = mongo_state_manager  # alias for backward compatibility with tests
```

---

#### `backend/orchestrator/confidence.py`

**What it is:** Confidence math, RCA text generation, and remediation fix templates.

**`calculate_overall_confidence(agent_confidences)`:**
- Input: `{"cicd": 0.85, "kubernetes": 0.92}`
- Returns: `max(values)` = `0.92`
- **Why max and not average?** If one agent is very confident, the investigation can stop. Using a noisy-OR formula (1 - product of (1-p)) would inflate confidence artificially as more agents are added — which is not what we want.

**`get_confidence_level(overall_confidence)`:**
- `>= 0.9` → `"very_high"` | `>= 0.75` → `"high"` | `>= 0.5` → `"medium"` | `>= 0.25` → `"low"` | else → `"very_low"`

**`synthesize_rca(investigation)`** — Fallback when LLM fails:
1. Finds the `AgentFinding` with the highest confidence (primary finding)
2. Collects contributing factors from all findings
3. Builds a timeline from findings + routing decisions
4. Uses templates per `HypothesisType`:
   - `DEPLOYMENT_INDUCED_FAILURE` → "A recent software release appears to have caused the problem..."
   - `KUBERNETES_OOM` → "The service appears to have run out of memory and stopped..."
   - `APPLICATION_ERROR` → "The application appears to have hit an error..."
   - etc.

**`generate_remediation(rca)`** — Fallback fix plans per root cause type:
- `DEPLOYMENT_INDUCED_FAILURE` → rollback steps
- `KUBERNETES_OOM` → memory limit increase steps
- `APPLICATION_ERROR` → hotfix steps
- `TRAFFIC_INCIDENT` → scale-up + rate limiting steps
- etc.

---

### 4.7 Agents

---

#### `backend/agents/cicd/agent.py` — `CICDAgent`

**What it is:** A deterministic (rule-based, no AI) agent that analyzes CI/CD evidence. Used as fallback when the LLM fails.

**Rules applied (`_analyze_evidence`):**
- Config change with "memory" or "limit" in description → `DEPLOYMENT_INDUCED_FAILURE`, confidence 0.90
- Any deployment evidence → `DEPLOYMENT_INDUCED_FAILURE`, confidence 0.80
- Code change only → `APPLICATION_ERROR`, confidence 0.70
- Dependency change → `DEPENDENCY_ISSUE`, confidence 0.75
- No evidence → `UNKNOWN`, confidence 0.10

Returns an `AgentFinding` object.

---

#### `backend/agents/kubernetes/agent.py` — `KubernetesAgent`

**What it is:** Deterministic agent for Kubernetes evidence.

**Rules:**
- `exit_code == 137` → OOMKilled → `KUBERNETES_OOM`, confidence 0.95
- `restart_count > 5` → likely OOM → confidence 0.85
- Pod event reason `OOMKilling` or `OutOfMemory` → confidence 0.95
- Memory usage > 90% of limit → confidence 0.90

---

#### `backend/agents/observability/agent.py` — `ObservabilityAgent`

**What it is:** Deterministic agent for metrics, logs, and traces.

**Rules:**
- P99 latency > 2000ms → confidence 0.85
- Error rate > 10% → confidence 0.90
- Both high latency + high error rate → `TRAFFIC_INCIDENT`, confidence 0.85
- Stack trace present → `APPLICATION_ERROR`, confidence 0.85
- Slow trace (> 5000ms) → confidence 0.80

---

#### `backend/agents/markdown/` — LLM Prompt Definitions

**What they are:** Markdown files that define how each LLM-powered agent should think and respond. They are loaded at runtime, combined with current evidence/context, and sent to the LLM as the system prompt + user message.

| File | What it defines |
|------|----------------|
| `router.md` | How to choose the next agent; gap→agent mapping rules; output schema |
| `cicd_analyzer.md` | How to analyze deployment/config/code evidence; output schema |
| `kubernetes_analyzer.md` | How to analyze pod exit codes, restart counts, resource usage; output schema |
| `observability_analyzer.md` | How to analyze latency, error rates, logs, traces; output schema |
| `rca_synthesizer.md` | How to write a plain-English root cause explanation from all agent findings |
| `remediation_planner.md` | How to generate a step-by-step remediation plan |

Each file defines: **Role**, **Inputs**, **Workflow** (reasoning steps), **Output Format** (JSON schema), **Constraints** (rules the LLM must follow).

Example constraints from `router.md`:
- Must select from `available_agents` only
- Must NOT select an already-invoked agent unless justified by new evidence
- Must reference specific evidence gaps in the reasoning

---

### 4.8 LLM Layer

---

#### `backend/llm/base.py`

**What it is:** An abstract base class (interface) that every LLM provider must implement. This is how you can swap between mock and real LLM without changing any other code.

**What it defines:**
```python
class LLMProvider(ABC):
    async def generate(request: LLMRequest) -> LLMResponse     # send prompt, get text back
    async def generate_structured(request, model) -> BaseModel  # send prompt, get typed object
    provider_name: str   # "mock" or "nemotron"
    model_name: str      # "mock-llm" or "nemotron-3-ultra"
```

**`LLMRequest`** — What you send:
```
prompt        → the user message content
system_prompt → the AI's persona/instructions
temperature   → 0.1 (low = deterministic/consistent, high = creative/random)
max_tokens    → max length of response
metadata      → extra info for tracing (task type, incident_id)
```

**`LLMResponse`** — What comes back:
```
content      → the text response
tokens_used  → how many tokens were consumed (cost tracking)
model        → which model responded
```

---

#### `backend/llm/mock.py`

**What it is:** A fake LLM for development and testing. Returns pre-canned JSON responses without making any real API calls.

**`MockLLM`** — General purpose:
- `set_response(key, response)` — lets tests inject specific responses
- `_default_response(prompt)` — pattern-matches keywords and returns canned JSON:
  - "route" in prompt → `{"selected_agent": "cicd", "reasoning": "Mock routing", ...}`
  - "analyze" in prompt → `{"finding": "Mock analysis finding", "confidence": 0.75, ...}`
  - "root cause" → template RCA JSON
  - "remediation" → template remediation JSON

**`DeterministicMockLLM`** — Smarter mock with keyword routing rules:
- If "deployment" in prompt → route to `cicd`
- If "oom" or "memory" in prompt → route to `kubernetes`
- If "latency" or "p99" in prompt → route to `observability`
- Returns realistic canned responses for each scenario
- Zero delay — instant responses for fast tests

---

#### `backend/llm/nemotron.py` — `NemotronLLM`

**What it is:** The real LLM provider. Calls NVIDIA's Nemotron 3 Ultra model via the OpenAI-compatible API. Only used in Phase 13 (production mode).

**How it works:**
1. Uses the `openai` Python SDK with `base_url` set to NVIDIA's endpoint
2. `generate(request)`:
   - Builds `messages` with `{"role": "system", ...}` and `{"role": "user", ...}`
   - Calls `client.chat.completions.create(...)`
   - Extracts `response.choices[0].message.content`
   - Calls `_write_trace()` to optionally log the call

**Trace logging (`_write_trace`):**
- Only active when `settings.llm_trace_enabled = True`
- Appends one JSON line to `logs/llm_traces.jsonl` per call
- Each line contains: trace_id, timestamp, model, task metadata, full system_prompt, full user prompt, response text, tokens used, duration in ms, any error
- Uses `asyncio.Lock` so parallel calls don't corrupt the file
- Errors writing the trace file are silently swallowed — a trace failure must never interrupt an actual investigation

**Error handling:** If the API call throws any exception, it's caught and returned as `LLMResponse(content="Error: ...")`. The calling code (`AgentRunner`) sees the error string, fails JSON parsing, and falls back to the deterministic Python agent.

---

#### `backend/llm/__init__.py`

**What it is:** A factory function. Returns the right LLM based on config.

```python
def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "nemotron":
        return NemotronLLM(api_key=settings.nemotron_api_key, ...)
    else:
        return MockLLM()  # default for all non-production environments
```

---

#### `backend/llm/schemas.py`

**What it is:** Pydantic models for validating structured JSON output from the LLM.

| Schema | Used for |
|--------|---------|
| `AgentAnalysisResponse` | Parsing JSON from CICD/K8s/Observability agents |
| `RoutingDecisionResponse` | Parsing JSON from the router agent |
| `RCAResponse` | Parsing JSON from the RCA synthesizer |
| `RemediationResponse` | Parsing JSON from the remediation planner |

If the LLM returns malformed JSON, `model_validate_json()` raises an exception and `AgentRunner` catches it and uses the deterministic fallback.

---

### 4.9 Runtime

---

#### `backend/runtime/agent_loader.py` — `AgentDefinitionLoader`

**What it is:** Reads all `.md` files from `backend/agents/markdown/` into memory at startup.

**How it works:**
- `load_all()`: scans the directory for `*.md` files, reads each as text, stores in `_cache: Dict[str, str]` where key = filename without `.md` extension
- Results are cached — subsequent calls return instantly from memory
- `reload()` — clears cache and re-reads all files from disk (useful for hot-reloading prompts without restarting the server)

**Result after loading:**
```python
{
    "router":                "# Router Agent\n## Role\n...",
    "cicd_analyzer":         "# CICD Analyzer\n...",
    "kubernetes_analyzer":   "...",
    "observability_analyzer":"...",
    "rca_synthesizer":       "...",
    "remediation_planner":   "..."
}
```

---

#### `backend/runtime/agent_runner.py` — `AgentRunner`

**What it is:** The execution engine for all LLM-powered agents. Takes a Markdown agent definition + current evidence → builds a prompt → calls the LLM → parses the JSON response → returns a typed Python object.

**Constructor:**
```python
AgentRunner(agent_definitions: Dict[str, str])
self.llm = get_llm_provider()  # MockLLM or NemotronLLM
```

**`_build_prompt(agent_name, input_data, output_schema)`:**
1. Gets the Markdown definition for the agent from `agent_definitions`
2. Appends the current input data serialized as JSON
3. Appends the required output JSON schema
4. Returns the complete prompt string

**`run_analysis_agent(agent_name, incident, evidence, previous_findings)`:**
1. Maps agent name to `AgentType` (e.g. `"cicd_analyzer"` → `AgentType.CICD`)
2. Formats evidence as a text summary (last 10 items)
3. Formats previous findings as a text summary (last 5 items)
4. Builds and sends prompt to LLM
5. Parses response with `AgentAnalysisResponse.model_validate_json()`
6. Returns `AgentFinding`
7. **On any parse failure** → calls `_run_deterministic_fallback()` which instantiates the appropriate Python agent class

**`run_router_agent(...)`:**
1. Builds routing context as JSON (incident, hypothesis, gaps, available agents, evidence summary)
2. Calls LLM with `router.md` prompt
3. Parses `RoutingDecisionResponse`
4. Returns `(AgentType, reasoning_string)`
5. On failure → returns `(available_agents[0], "Fallback")`

**`run_rca_agent(...)`:**
1. Formats all investigation data as JSON
2. Calls LLM with `rca_synthesizer.md` prompt
3. Parses `RCAResponse`, returns `RootCauseAnalysis`
4. On failure → calls `synthesize_rca()` from `confidence.py`

**`run_remediation_agent(...)`:**
1. Calls LLM with `remediation_planner.md` prompt
2. Parses `RemediationResponse`, returns `RemediationRecommendation`
3. On failure → calls `generate_remediation()` from `confidence.py`

**Global singleton:**
```python
_runner: Optional[AgentRunner] = None

async def get_agent_runner() -> AgentRunner:
    global _runner
    if _runner is None:
        definitions = load_all_agent_definitions()
        _runner = AgentRunner(definitions)
    return _runner
```
Created once when first needed, reused for the server's lifetime.

---

### 4.10 Services

---

#### `backend/services/mongodb.py`

**What it is:** Sets up the Beanie ODM with Motor (async MongoDB driver) on server startup.

**`MongoDB` class:**
- `connect()`:
  1. Creates `AsyncIOMotorClient(settings.mongodb_uri)` — opens connection pool
  2. Calls `init_beanie(database, document_models=[...])` — registers all 9 Document classes, creates indexes
- `close()` — closes the connection pool

**Called from `main.py`'s `lifespan` function:**
```python
await mongodb.connect()  # on startup
await mongodb.close()    # on shutdown
```

---

#### `backend/services/investigation_service.py` — `InvestigationService`

**What it is:** The top-level coordinator. This is what the API routes call when a new investigation needs to be started.

**`start_investigation(incident, max_iterations, evidence)`:**
1. If `evidence` is provided externally (e.g. from GitHub monitor) → use it directly
2. Otherwise → requires GitHub config in settings, then calls `get_cicd_evidence_from_github(incident)` to fetch CI/CD evidence
3. Calls `mongo_state_manager.create_state(incident, max_iterations, evidence=github_evidence)` → saves to MongoDB
4. Builds the `graph_input` dict for LangGraph
5. Broadcasts `"running"` status and 0% progress via WebSocket
6. Calls `_run_graph_with_events(graph_input, max_iterations)` → runs the full LangGraph pipeline
7. After graph finishes → calls `mongo_state_manager.update_state(final_state)` → saves results to MongoDB
8. Broadcasts final status change
9. Returns the completed `InvestigationState`

**`_run_graph_with_events(graph_input, max_iterations)`:**
- Uses LangGraph's `graph.astream(graph_input, config={"recursion_limit": 50})` to run the graph step by step
- For each step received from the stream:
  - Broadcasts progress update
  - If step is `"route"` → broadcasts routing decision
  - If step is an agent node → broadcasts agent finding
  - If step is `"evaluate"` → broadcasts updated confidence

**`list_investigations(status)`:** Calls `mongo_state_manager.list_states_lite(status)` — lightweight load, no evidence/findings loaded.

**Global singleton:**
```python
investigation_service = InvestigationService()
```

---

#### `backend/services/github_monitor.py` — `GitHubActionsMonitor`

**What it is:** A background `asyncio.Task` that polls GitHub Actions every N seconds (default 60s) for failed workflow runs. When it finds a new failure, it automatically creates an AgentOps incident and starts an investigation — no human needed.

**`ProcessedRunTracker`:**
- Maintains a set of already-processed GitHub `run_id` values
- On startup: loads existing IDs from MongoDB's `processed_runs` collection (survives server restarts)
- `mark_processed(run_id, ...)` — adds to set and persists to MongoDB

**`GitHubActionsMonitor`:**
- `start()` → spawns `_monitor_loop()` as a background `asyncio.Task`
- `_monitor_loop()` — every `poll_interval_seconds`:
  1. Fetches recent workflow runs from GitHub API
  2. Filters to FAILED + not yet processed
  3. For each: calls `_create_incident_from_run(run)`
  4. `_create_incident_from_run()`:
     - Fetches full evidence (job logs, commits)
     - Creates `Incident` with title `"CI/CD Failure: {workflow_name}"`, severity based on branch
     - Calls `investigation_service.start_investigation(incident, evidence=github_evidence)`
     - Marks run as processed
- `stop()` → cancels the background task

**Activated from `main.py` only if `settings.github_token` is set.** If no token is configured, the monitor simply doesn't start.

---

### 4.11 Tools / Data Access

---

#### `backend/tools/data_access.py`

**What it is:** The evidence loading layer — a collection of functions that return `List[Evidence]` from various sources.

**`DataLoader` class:**
- Takes `data_dir` from `settings.data_dir` (defaults to `/app/data`)
- `load_kubernetes_data(incident_id)` → reads `data/kubernetes/{incident_id}.json`
- `load_cicd_data(incident_id)` → reads `data/cicd/{incident_id}.json`
- `load_observability_data(incident_id)` → reads `data/observability/{incident_id}.json`

**Evidence creation functions:**

`get_kubernetes_evidence(incident)`:
- Loads the K8s fixture file for `incident_id`
- Creates `Evidence` objects:
  - Pod with `exit_code` field → `EvidenceType.POD_EXIT_CODE`
  - Pod with `restart_count` field → `EvidenceType.POD_RESTART_COUNT`
  - Pod events list → `EvidenceType.POD_EVENT` per event
  - Memory `usage` + `limit` fields → `EvidenceType.RESOURCE_USAGE` + `RESOURCE_LIMIT`

`get_observability_evidence(incident)`:
- Loads the observability fixture file
- Creates Evidence for: `latency`, `error_rate`, `log` (per log entry), `stack_trace`, `trace`

`get_cicd_evidence_from_fixture(incident)`:
- Loads the CI/CD fixture file
- Creates Evidence for: `deployment`, `code_change`, `config_change`, `dependency_change`

`get_cicd_evidence_from_github(incident)` (async):
- Calls `GitHubActionsClient` to fetch workflow runs, jobs, commits within the time window
- Normalizes with `normalize_to_agentops_cicd_schema()`
- Creates same Evidence types as fixture version
- Requires `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO` in settings

`get_cicd_evidence(incident)` — sync convenience wrapper:
1. Tries fixture file first — if data found, returns it immediately
2. If no fixture → runs the async GitHub fetch in the event loop
3. If GitHub fails → logs a warning and returns empty list

---

### 4.12 Data Sources

---

#### `backend/data_sources/github_actions/`

**What it is:** A complete GitHub REST API client with:

- **`__init__.py`** — exports `GitHubActionsClient`, `GitHubAPIError`, `RateLimitError`
- **`client.py`** — `GitHubActionsClient` async context manager:
  - `fetch_workflow_runs(owner, repo, branch, since)` → paginated list of workflow runs
  - `fetch_workflow_jobs(owner, repo, run_id)` → jobs within a run
  - `fetch_run_logs(owner, repo, run_id)` → raw log text
  - `fetch_commits(owner, repo, since)` → recent commits
  - `fetch_cicd_data_for_incident(owner, repo, incident_time, time_window_hours)` → bundles all of the above into one call, filtered to the incident's time window
- **`models.py`** — Pydantic models for GitHub API response shapes: `WorkflowRun`, `WorkflowJob`, `Commit`, `DeploymentStatus`
- **`adapter.py`** — `normalize_to_agentops_cicd_schema(github_data)` converts raw GitHub API objects into the internal AgentOps format with `deployments`, `code_changes`, `config_changes`, `dependency_changes` lists

---

## 5. ASCII Flow Diagram — Full Investigation Pipeline

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                         TRIGGERS                                    │
  │                                                                     │
  │  [Human / Frontend]              [Background Monitor]               │
  │  POST /api/incidents    OR        github_monitor.py                  │
  │  { Incident JSON }               polls GitHub every 60s             │
  │         │                        finds FAILED workflow run          │
  │         │                        creates Incident automatically     │
  │         └────────────────┬────────────────────┘                    │
  └─────────────────────────│───────────────────────────────────────────┘
                             │
                             ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  services/investigation_service.py                               │
  │                                                                  │
  │  1. Fetch GitHub CI/CD evidence                                  │
  │     get_cicd_evidence_from_github(incident)                      │
  │     → tools/data_access.py                                       │
  │     → data_sources/github_actions/client.py (GitHub REST API)   │
  │                                                                  │
  │  2. mongo_state_manager.create_state(incident, evidence)         │
  │     → saves Incident + InvestigationState to MongoDB             │
  │                                                                  │
  │  3. broadcast_status_change("running")    [WebSocket]            │
  │  4. broadcast_progress(0, 5, 0.0)         [WebSocket]            │
  │                                                                  │
  │  5. graph.astream(graph_input)  ← starts the LangGraph pipeline  │
  └──────────────────────────────────────────────────────────────────┘
                             │
                             ▼
  ╔══════════════════════════════════════════════════════════════════╗
  ║       LANGGRAPH INVESTIGATION PIPELINE                           ║
  ║       orchestrator/graph.py                                      ║
  ║                                                                  ║
  ║  ┌───────────────────────────────┐                               ║
  ║  │ 1. NORMALIZE                  │ Sets status = RUNNING         ║
  ║  └───────────────┬───────────────┘                               ║
  ║                  │                                               ║
  ║  ┌───────────────▼───────────────┐                               ║
  ║  │ 2. PRE_FILTER (rule-based)    │ Scans title + description     ║
  ║  │                               │ for keywords                  ║
  ║  │  "deploy" → DEPLOYMENT_FAILURE│                               ║
  ║  │  "oom"    → KUBERNETES_OOM    │                               ║
  ║  │  "5xx"    → TRAFFIC_INCIDENT  │                               ║
  ║  │  "config" → CONFIG_ERROR      │                               ║
  ║  │                               │ Sets evidence_gaps list       ║
  ║  └───────────────┬───────────────┘                               ║
  ║                  │                                               ║
  ║  ┌───────────────▼───────────────┐                               ║
  ║  │ 3. LOAD_EVIDENCE              │ tools/data_access.py          ║
  ║  │                               │                               ║
  ║  │  get_kubernetes_evidence()    │ → loads K8s fixture JSON      ║
  ║  │  get_observability_evidence() │ → loads obs fixture JSON      ║
  ║  │  (CI/CD already loaded)       │                               ║
  ║  └───────────────┬───────────────┘                               ║
  ║                  │                                               ║
  ║  ┌───────────────▼───────────────┐  ◄──────────────────┐        ║
  ║  │ 4. ROUTE (adaptive router)    │                      │        ║
  ║  │                               │ LLM call:            │        ║
  ║  │  AgentRunner.run_router_agent │ router.md prompt     │        ║
  ║  │  + current evidence           │ + evidence summary   │        ║
  ║  │  + evidence_gaps              │ + gaps               │        ║
  ║  │                               │                      │        ║
  ║  │  Fallback: router.py          │ deterministic rules  │        ║
  ║  │  gap → agent mapping          │ if LLM fails         │        ║
  ║  └──┬──────────────┬────────┬────┘                      │        ║
  ║     │              │        │                            │        ║
  ║     │   conditional│edges   │                            │        ║
  ║     ▼              ▼        ▼                            │        ║
  ║  ┌──────┐  ┌───────────┐  ┌─────────────────┐          │        ║
  ║  │ 5a.  │  │   5b.     │  │      5c.        │          │        ║
  ║  │ CICD │  │KUBERNETES │  │ OBSERVABILITY   │          │        ║
  ║  │AGENT │  │  AGENT    │  │    AGENT        │          │        ║
  ║  │      │  │           │  │                 │          │        ║
  ║  │ LLM: │  │  LLM:     │  │ LLM:            │          │        ║
  ║  │cicd_ │  │k8s_       │  │ obs_analyzer.md │          │        ║
  ║  │anal. │  │anal.md    │  │                 │          │        ║
  ║  │.md   │  │           │  │ Fallback:       │          │        ║
  ║  │      │  │ Fallback: │  │ ObservabilityAg.│          │        ║
  ║  │Fall: │  │ Kubernets │  │ (Python rules)  │          │        ║
  ║  │CICDAg│  │ Agent     │  └────────┬────────┘          │        ║
  ║  └──┬───┘  └────┬──────┘           │                   │        ║
  ║     │           │                  │                   │        ║
  ║     └─────┬─────┴──────────────────┘                   │        ║
  ║           │  each produces AgentFinding                │        ║
  ║           │  (hypothesis + confidence 0.0–1.0)         │        ║
  ║           ▼                                            │        ║
  ║  ┌─────────────────────────────────────────────┐       │        ║
  ║  │ 6. EVALUATE                                 │       │        ║
  ║  │                                             │       │        ║
  ║  │  overall_confidence = max(agent_scores)     │       │        ║
  ║  │  e.g. max(0.85_cicd, 0.92_k8s) = 0.92      │       │        ║
  ║  │                                             │       │        ║
  ║  │  Append ConfidenceEntry snapshot            │       │        ║
  ║  │                                             │       │        ║
  ║  │  IF confidence >= 0.75 ──────────┐          │       │        ║
  ║  │  IF iterations >= 5   ──────────►│generate  │       │        ║
  ║  │  ELSE ────────────────────────────┼──────────┼───────┘        ║
  ║  └─────────────────────────────┬────┘          │               ║
  ║                                │  loop back    │               ║
  ║                                ▼               ▼               ║
  ║  ┌──────────────────────────────────────────────────────────┐  ║
  ║  │ 7. GENERATE_RCA                                          │  ║
  ║  │                                                          │  ║
  ║  │  AgentRunner.run_rca_agent()                             │  ║
  ║  │    → LLM: rca_synthesizer.md + all findings              │  ║
  ║  │    → Fallback: synthesize_rca() template logic           │  ║
  ║  │                                                          │  ║
  ║  │  AgentRunner.run_remediation_agent()                     │  ║
  ║  │    → LLM: remediation_planner.md + root cause type       │  ║
  ║  │    → Fallback: generate_remediation() template           │  ║
  ║  └─────────────────────────────┬────────────────────────────┘  ║
  ║                                │                               ║
  ║  ┌─────────────────────────────▼────────────────────────────┐  ║
  ║  │ 8. PERSIST  (no-op in graph; actual save in service)     │  ║
  ║  └─────────────────────────────┬────────────────────────────┘  ║
  ║                                │                               ║
  ║                               END                              ║
  ╚════════════════════════════════╪════════════════════════════════╝
                                   │
                                   ▼
  ┌──────────────────────────────────────────────────────────────────┐
  │  Back in investigation_service.py                                │
  │                                                                  │
  │  mongo_state_manager.update_state(final_state)                   │
  │  → saves to MongoDB:                                             │
  │    investigations, evidence, agent_findings,                     │
  │    routing_decisions, confidence_history,                        │
  │    root_cause_analyses, remediations                             │
  │                                                                  │
  │  broadcast_status_change("completed")  [WebSocket]               │
  └──────────────────────────────────────────────────────────────────┘
```

---

### WebSocket Real-Time Update Flow

```
  Browser Dashboard                          backend/events.py
        │                                         │
        │── WebSocket connect ───────────────────►│  connection_manager.connect()
        │                                         │
        │◄── initial_state ──────────────────────│  sends current snapshot
        │                                         │
        │    ┌── Investigation graph runs ────────────────────────────┐
        │    │                                                         │
        │    │  graph step "route" completes                           │
        │    │    → broadcast_routing_decision()  ────────────────────►│
        │◄───┤     { type: "routing_decision",                        │
        │    │       selected_agent: "kubernetes",                     │
        │    │       reasoning: "OOM evidence gap requires K8s agent"} │
        │    │                                                         │
        │    │  graph step "invoke_kubernetes" completes               │
        │    │    → broadcast_agent_finding()     ────────────────────►│
        │◄───┤     { type: "agent_finding",                           │
        │    │       agent_type: "kubernetes",                         │
        │    │       finding: "Pod was OOMKilled (exit code 137)",     │
        │    │       confidence: 0.92 }                                │
        │    │                                                         │
        │    │  graph step "evaluate" completes                        │
        │    │    → broadcast_progress()          ────────────────────►│
        │◄───┤     { iteration: 2, max: 5,                            │
        │    │       overall_confidence: 0.92,                         │
        │    │       progress_percent: 40.0 }                          │
        │    │                                                         │
        │    │  Investigation complete                                  │
        │    │    → broadcast_status_change()     ────────────────────►│
        │◄───┤     { status: "completed" }                            │
        │    └─────────────────────────────────────────────────────────┘
        │                                         │
        │── {"type": "ping"} ─────────────────────►│
        │◄── {"type": "pong"} ───────────────────│  keep-alive
```

---

## 6. Key Concepts Glossary

| Term | Plain English |
|------|--------------|
| **Incident** | A production problem. E.g. "payment-service OOMKilled at 3am" |
| **Investigation** | The automated analysis process triggered by an incident |
| **Evidence** | One verifiable fact: "Pod exited with code 137", "Config changed memory to 512Mi" |
| **AgentFinding** | What a specialist concludes: "Pod OOMKilled due to memory limit reduction" with confidence 0.92 |
| **HypothesisType** | The system's best current guess for WHY the incident happened |
| **EvidenceGap** | Something we don't yet know: "we have no deployment data yet" |
| **RoutingDecision** | The choice of which specialist agent to call next, and why |
| **ConfidenceEntry** | Snapshot: at iteration 2, CICD=0.85, K8s=0.92, overall=0.92, sufficient=True |
| **RCA** | Root Cause Analysis — the final "what happened and why" report |
| **Remediation** | The fix plan with prioritized steps |
| **LangGraph** | Framework for defining the investigation as a directed graph (flowchart of async functions) |
| **Beanie** | Python library that maps Python objects to MongoDB documents (ODM) |
| **WebSocket** | A persistent two-way connection between browser and server for live streaming |
| **Mock LLM** | A fake AI that returns rule-based canned responses — used when developing/testing |
| **Nemotron** | NVIDIA's AI model — the real LLM used in production |
| **Deterministic fallback** | When the LLM fails or returns bad JSON, the system falls back to Python rule-based logic |
| **Fixture data** | Pre-made JSON files in `data/` that simulate real Kubernetes/observability/CI-CD data for testing |
| **Confidence threshold** | 0.75 by default — once any agent is ≥75% confident, investigation stops and RCA is generated |
| **max_iterations** | 5 by default — even if confidence never reaches 0.75, investigation stops after 5 rounds |
| **Structured output** | When the LLM is explicitly asked to respond in JSON matching a specific schema (not free text) |
| **AgentRunner** | The runtime that loads `.md` prompts, calls the LLM, parses JSON output into typed Python objects |
| **Evidence gap resolution** | When an agent collects evidence that covers a gap (e.g. finding pod exit code covers the "pod_memory_status" gap), that gap is removed from the list |

---

*Generated: October 2026. Team: Neil Sulhyan, Huma Naaz Mohammad, Dhriti Shah.*
