# Decisions log

Format: what changed, why. Newest first.

## 2026-10-26 — Investigations stuck at `pending`, no collections on Atlas

### Findings (diagnosis)
Current flow: `GitHubActionsMonitor` (polls every 60s) -> failed run -> `IncidentDoc` + `ProcessedRunDoc`
-> `InvestigationService.start_investigation` (inserts `InvestigationDoc` with status `pending`, then fires
`_run_investigation` as a background task) -> LangGraph: normalize (sets `running`) -> pre_filter -> load_evidence
-> route -> invoke_agent -> evaluate -> generate_rca. Status in Mongo is only updated after each node completes.

1. **No collections on the cluster**: `docker-compose.yml` (uncommitted change) hard-coded
   `MONGODB_URI=mongodb://mongodb:27017`, so the backend container ignored the Atlas URI in `.env` and wrote
   everything (24 incidents/investigations) to the local compose Mongo. Atlas had no `agentops` database at all.
2. **Everything `pending`**: the running `agentops-backend` image was built 2026-10-20 (before the dynamic-agents
   refactor), so the container ran *old* code (`AgentType` enum etc.; 4 files differ from the working tree).
   The old image also lacks `openai`, so the router crashes in `get_llm_provider()` (`ModuleNotFoundError: openai`)
   before any finding/routing decision is persisted. Result: 24 investigations, 0 findings/routing decisions/RCAs.
3. **Why it could not be rebuilt**: `backend/requirements.txt` line 1 lost its `#`
   ("AgentOps Backend Dependencies" parsed as a package name), so `pip install -r` failed on every build.
   `openai==1.35.7` had been added to the file but never made it into an image.

### Changes
- `docker-compose.yml`: `MONGODB_URI=${MONGODB_URI:-mongodb://mongodb:27017}` — honour `.env` (Atlas) and fall back
  to the local container only when unset. Also pass `GITHUB_POLL_INTERVAL_SECONDS` (the setting existed but
  was never forwarded into the container).
- `backend/requirements.txt`: restored `#` on line 1 so the image can build.

### Not done / open
- **Backend image not rebuilt**: host disk is 100% full (`no space left on device` during build). The backend
  container is stopped on purpose (it was writing stale-code `pending` records into Atlas).
  Next: free disk, `docker compose build backend && docker compose up -d backend`.
- 8 stale `pending` investigations (+8 incidents, 8 processed_runs, 16 evidence) were written to Atlas by the old
  image before it was stopped. Delete them (or drop `agentops` DB on Atlas) before the real run, otherwise
  `processed_runs` makes the monitor skip those runs and they stay `pending` forever.
- The 24 old records in the local compose Mongo volume are untouched.
- `load_evidence` -> `get_cicd_evidence` falls back to a blocking `run_until_complete` GitHub fetch (hundreds of
  `/jobs` calls) when no GitHub evidence is attached; consider removing that fallback for monitor-created incidents.
- Credentials (Atlas password, GitHub/Nemotron tokens) sit in plaintext in `.env`; rotate them if this repo or
  these logs are ever shared.
