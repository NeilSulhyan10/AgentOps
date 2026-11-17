# Critic report: independent review of the investigation flow

An independent reviewer (a read-only subagent) ran the real graph on all 14 scenarios, ran the test suite, injected failures, and read the code. Every finding below was verified by running it unless marked *by reading*. This page records what it found and what has been done since.

**Status key:** fixed = changed and covered by tests where practical. open = known, not changed.

## Does the flow work end to end?

Yes: all 14 scenarios ran through every node without an exception. But in rules mode only 5 of 14 predicted the ground-truth root cause, for the reasons in findings 7 and 8. Every run ended `completed`, including the wrong ones.

**Update:** findings 7 and 8 are now fixed. The rule-based specialists classify evidence by kind, the root-cause type is decided from the whole causal chain, and rules mode matches all seven ShopLite scenarios (13 of the 15 scenarios overall; `tests/test_rules.py` pins this).

The rules-mode critic always challenges round 1 ("single layer") and cannot challenge in round 2, so every rules-mode run has the same shape: two specialists, one loop back. This is expected behaviour; the flow report shows a loop-back challenge as green because it is the critic doing its job.

## Findings

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | bug | `evaluate` set status `completed` before the critic and RCA ran, so "completed with no RCA" was observable and `trigger_incident.py --wait` could stop early | **fixed**: only `generate_rca` sets a finished status |
| 2 | bug | WebSocket connect crashed: it read `investigation.current_agent`, which does not exist | **fixed** (uses the last invoked agent) |
| 3 | bug (LLM mode) | Evidence truncation keeps the *last* 40 items (router: last 10); CI/CD evidence is loaded first so it is dropped. On incident-001 all 6 CI/CD items vanish from prompts | open |
| 4 | bug | JSON in a ` ```json ` fence was rejected; a failed LLM call became content `"Error: ..."` and the run looked successful | **fixed**: JSON is extracted from fences/prose; provider errors set `LLMResponse.error` and are logged as a fallback |
| 5 | bug | RCA fallback chose the lead finding by max confidence over *all* findings, including ungrounded ones (e.g. a fake-evidence finding at 0.99 decided the RCA) | **fixed**: only grounded findings are used |
| 6 | bug | A final `challenged` verdict still ends `completed`; two different confidence numbers; `INSUFFICIENT_EVIDENCE` is never set | open (visible in reports as an amber `critique`) |
| 7 | bug | Rule-based Kubernetes agent can only say `kubernetes_oom` or `unknown`; any restart or event gives OOM at 0.7 to 0.95. Causes the S4 to S7 mismatches | **fixed**: Kubernetes, CI/CD and observability rules classify by kind (OOM, startup crash, missing config, dependency, healthy); `orchestrator/causal.py` decides the type (mechanism > trigger > symptom; several mechanisms + a trigger = multi-layer) |
| 8 | bug | Pre-filter matches substrings with no negation: "healthy (no OOM)" becomes `kubernetes_oom` | **fixed**: clauses after no/not/without are ignored; "crashloop" no longer implies OOM |
| 9 | bug | `current_hypothesis` is set once by the pre-filter and never updated | open |
| 10 | bug | `completed_at` equalled `created_at` (stale in-memory timestamp) | **fixed** |
| 11 | fragile | A missing CI/CD fixture silently triggered a live GitHub fetch inside a graph node | **fixed**: `load_evidence` reads fixtures only; the GitHub fetch stays in the async service path |
| 12 | fragile | Only specialists logged their failures; router/critic/RCA exceptions left no flow event | **fixed**: every node is wrapped and writes `node_failed` with the node name |
| 13 | fragile | Persistence failures only logged a warning; the background task reference was not kept | partly fixed (task reference kept); persistence failure still only a warning |
| 14 | bug | `analyze_flow.py` attributed id-less events to the last run of an incident and double-counted fallbacks | **fixed**: events carry their investigation id; script rewritten on the new trace code |
| 15 | bug | Persisted `RoutingDecision.iteration` was 0-based, everything else 1-based | **fixed** |
| 16 | bug | `POST /api/incidents` without GitHub settings returned HTTP 500 | open |
| 17 | bug (*by reading*) | Frontend types agents as `cicd`/`kubernetes`/`observability`; the backend sends `cicd_analyzer` etc., so the "N of 3 agents" card never matches | **fixed**: agent names are plain strings; labels and colours work for any agent, including spawned ones; the card lists the agents that actually ran |
| 18 | fragile | `NemotronLLM(api_url=None)` raises `AttributeError` on first use; an unknown `LLM_PROVIDER` silently became the mock | partly fixed (unknown provider now warns; the crash is now reported as `node_failed`); no startup validation yet |
| 19 | fragile | Overall confidence = max grounded self-reported confidence, so one confident specialist always passes; grounding logic exists in three places | **fixed**: a defined formula (`orchestrator/scoring.py`) scores each finding from evidence and combines them with corroboration, contradiction, open gaps and the critic; grounding still has two copies (`critic.py`, `graph.py`) |
| 20 | fragile (*by reading*) | `update_state` does one `find_one` per child record after every node (N+1) | open |
| 21 | clarity | Mock LLM branches (`ROUTE:`/`ANALYZE:`...) were unreachable; its "responses" were never valid | **fixed**: mock removed, replaced by `RulesOnlyLLM` and `FaultInjectingLLM` |
| 22 | clarity | "Just drop a .md file" is only partly true: agent names are hard-coded in routing tables, the critic, fallbacks and frontend | partly fixed: front-matter in the .md gives an agent its rules and its app-map layer; the dashboard no longer hard-codes names. The router and critic preference tables still name the built-ins |
| 23 | clarity | Dead code: `AgentType` enum, unused settings, unused `create_routing_decision`, no-op `persist`, `print("DEBUG")` in `state.py`, duplicate `LLMRequest`/`LLMResponse`, duplicate formatters | partly fixed (duplicate LLM types, unused settings, old flow logger and mock removed; rest open) |
| 24 | clarity | README referenced missing `docs/` and `.env.example`, stale phase notes; `config.py` defaults only worked on one machine; evaluation paths hard-coded to `/home/neil/...` | **fixed** for README and config; `evaluation/experiments/runner.py` paths open |

## Flow-log gaps found, and what was done

| Gap | Status |
|---|---|
| `llm_parse_fallback` had no investigation id (100 of 257 events) | **fixed** |
| No fallback event for remediation | **fixed** (all five LLM tasks go through one helper) |
| LLM *unreachable* indistinguishable from LLM *bad JSON* | partly fixed (both logged as a fallback, with the cause in the message) |
| No `investigation_started` / `investigation_finished` | **fixed** |
| Node exceptions logged only for specialists | **fixed** (`node_failed`) |
| Persistence failures not logged | open |
| `load_evidence` has no per-source counts or missing-fixture note | open |
| `agent_finding` / `critic` / `rca` do not record LLM vs rules as the source | open |
| No sequence number; tests polluted the shared log file | partly fixed (ordering by timestamp; tests now use a temp log) |

## Failure-injection results (before the fixes)

| Injection | What a developer saw |
|---|---|
| LLM returns prose | run completes; fallbacks logged without an investigation id |
| LLM returns valid JSON in a code fence | valid answer discarded, looked like garbage |
| Provider returns `"Error: ..."` for every call | run completes at 0.95, looked successful |
| Router/critic/RCA raises | run fails; nothing in the flow log |
| Router names an unknown agent | rule-based fallback, visible in the log |
| Specialist raises | run fails; `agent_failed` logged |
| Specialists cite non-existent evidence | `max_iterations_reached`, but the RCA still named a cause at 0.9 |
| Critic always challenges | one loop, then `completed` at 0.3 |
| `max_iterations=0` | straight to the RCA, `unknown` at 0.1 |

The same situations are now the injectable faults in `backend/faults.py`, and `docs/showcase/` shows how each one looks in a flow report.

## Test-suite findings

All fixed:

- 12 GitHub-client tests never ran (missing `patch`/`AsyncMock` imports hid them). Once they ran, they exposed a **product bug**: the retry decorator lacked `reraise=True`, so callers received `tenacity.RetryError` and their `except RateLimitError` handlers never fired. Fixed in `client.py`; the tests also patched `client.get` while the product calls `client.request`.
- Two settings tests asserted one developer's `.env` and `/home/neil/...` paths. Replaced by machine-independent checks.
- `test_rca_with_no_findings` asserted old wording. Updated.
- `test_no_mock_cicd_fixtures_exist` asserted the opposite of the product (it passed only because the path did not exist) and was removed.
- `test_state_manager` connected to whatever database `.env` named. It is now opt-in (`AGENTOPS_TEST_MONGO=1`).
- `pytest-asyncio==0.23.3` broke collection; pinned to 0.23.8.

Suite: 127 passed, 1 skipped (the opt-in database test).
