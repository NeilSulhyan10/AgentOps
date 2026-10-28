# Prompt: build "ShopLite", a target app for testing AgentOps

## Goal and why
AgentOps is a multi-agent DevOps incident investigator. A router agent picks specialists
(`cicd_analyzer`, `kubernetes_analyzer`, `observability_analyzer`), they read evidence,
and an RCA agent produces a root cause. Today it only runs on static JSON in `data/`.
I need a small, real, deliberately breakable application, with a real CI/CD pipeline,
that produces genuine failures with a KNOWN root cause. That lets me check whether
AgentOps routes to the right agents, finds the right cause, and how confident it is.

Build the app so every failure is injectable on demand and every failure has a written
ground-truth answer. Without ground truth I cannot score AgentOps.

## 1. The application
- Small web service in Python (FastAPI) or Node, three endpoints: `GET /health`,
  `GET /products`, `POST /orders`. A tiny dependency (Postgres or Redis, via docker
  compose) so a "dependency issue" scenario is possible.
- Config through environment variables only (`DB_URL`, `MEMORY_LIMIT_HINT`, `FEATURE_*`).
- Structured JSON logs to stdout (timestamp, level, request_id, route, latency_ms, error).
- Prometheus metrics at `/metrics`: request count, error count by status, latency
  histogram (p50/p95/p99). AgentOps' observability agent reads latency, error rate,
  logs, traces, so these must exist.
- A fault-injection endpoint or env flag set (`FAULT=oom|latency|crash|bad_config|db_down|none`)
  so a scenario can be triggered deterministically, not by luck.
- Unit tests (some intentionally flaky/failing via a flag), a Dockerfile, a `/version`
  endpoint returning git SHA and image tag (CI/CD evidence needs to link to a deploy).

## 2. Incident scenarios (each needs a ground-truth file)
Map to the hypothesis types AgentOps knows:

| ID | Scenario | How to trigger | Expected root cause type | Expected lead agent |
|---|---|---|---|---|
| S1 | Bad deployment | Commit that breaks startup / fails a test or build step | deployment_induced_failure | cicd_analyzer |
| S2 | Pod OOMKilled | `FAULT=oom` leaks memory; container memory limit 128Mi | kubernetes_oom | kubernetes_analyzer |
| S3 | Latency / 5xx spike | `FAULT=latency` adds sleeps and random 500s | traffic_incident / application_error | observability_analyzer |
| S4 | Config error | Remove/typo a required env var in the manifest or workflow | configuration_error | cicd + kubernetes |
| S5 | Dependency down | Stop the DB container / wrong `DB_URL` | dependency_issue | observability + kubernetes |
| S6 | Multi-layer | Bad deploy that also lowers memory limit and raises latency | multi_layer_failure | all three |
| S7 | Healthy control | No fault | none (AgentOps should not invent a cause) | n/a |

For each scenario write `ground_truth/S<n>.json` in the same shape as
`data/ground_truth/incident-001.json` in the AgentOps repo (copy its fields): root
cause type, expected agents, key evidence, expected remediation. Read that file
first and match its schema exactly.

## 3. Kubernetes
- Manifests (or a Helm chart) for Deployment, Service, ConfigMap, with resource
  requests/limits and liveness/readiness probes.
- Runs on `kind` or `minikube` locally, so no cloud account is needed.
- A script `scripts/export_k8s_evidence.sh` that dumps pod status, restart counts,
  last termination reason and exit code (137 for OOM), events, and `kubectl top`
  into JSON shaped like `data/kubernetes/incident-001.json`.

## 4. CI/CD: must run anywhere
AgentOps polls the **GitHub Actions API** (`GITHUB_OWNER`, `GITHUB_REPO`,
`GITHUB_TOKEN`) and turns failed workflow runs into incidents, so GitHub Actions is the
primary pipeline. But the logic must not be locked to it:
- Put every step in portable scripts/Makefile targets: `make lint`, `make test`,
  `make build`, `make push`, `make deploy`, `make smoke-test`. The CI file only calls these.
- Provide `.github/workflows/ci.yml` (lint, test, build, push) and
  `.github/workflows/deploy.yml` (deploy to kind/cluster, then smoke test), both calling the
  Makefile. Deploy workflow must have a name and jobs containing "deploy", since the AgentOps
  adapter detects deployment workflows by name and job names.
- Also provide equivalents that call the same Makefile: `.gitlab-ci.yml` and a `Jenkinsfile`,
  so the pipeline moves to any CI by swapping one thin file.
- Runs on a self-hosted or ubuntu runner, with `workflow_dispatch` inputs
  (`fault`, `memory_limit`, `break_config`) so any scenario can be fired from the UI or
  `gh workflow run` without editing code.
- Tag images with the git SHA and print it in logs. Print readable error output on failure
  (AgentOps fetches job logs). Do not mask failures with `continue-on-error`.
- A `scripts/run_scenario.sh S<n>` that triggers a scenario end to end, waits for the
  failure, and prints the run ID, so a test run is one command.
- Secrets only via CI secrets / `.env` (never committed). Provide `.env.example`.

## 5. Observability stack
Optional `docker-compose.observability.yml` with Prometheus + Grafana + Loki (or just
Prometheus and log files). A script `scripts/export_observability_evidence.sh` that
writes latency, error rate, and sample error logs into JSON shaped like
`data/observability/incident-001.json`.

## 6. Test harness
`scripts/evaluate.py`: for each scenario run it, collect evidence, call AgentOps
(`POST` to its investigation API), and compare the result with `ground_truth/S<n>.json`.
Report per scenario: correct root cause type (y/n), agents used vs expected, final
confidence, iterations, time taken. Output a table plus `results.json`. Use AgentOps'
`logs/flow.jsonl` (see `scripts/analyze_flow.py`) for the agent path.

## 7. Deliverables and acceptance
- Repo with README: setup in under 10 minutes, how to run each scenario, how to point
  AgentOps at it (env vars).
- Every scenario reproducible with one command and produces a failing run or unhealthy
  pod matching its ground truth.
- S7 produces no failure. All Makefile targets pass locally with no GitHub account.
- Do not hard-code secrets or commit tokens. Keep it small; prefer clarity over features.
