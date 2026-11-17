# Setup and tools

Everything needed to reproduce the flow reports and run the tests, with the versions used when this was written (2026-11-17, Fedora Linux). Referenced from the project report.

## Required

| Tool | Version used | Needed for | Install |
|---|---|---|---|
| Python | 3.12.15 (3.11+ works; the Dockerfile uses 3.11) | everything | system package |
| Python packages | pinned in `backend/requirements.txt` | everything | `python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt` |

Key pinned packages: fastapi 0.111.0, uvicorn 0.30.1, pydantic 2.7.4, langgraph 0.2.14, beanie 1.23.6, motor 3.3.2, openai 1.35.7, pytest 8.2.2, pytest-asyncio 0.23.8.

That is all that is needed for `scripts/investigate.py`, the flow reports, and the test suite. No database, no network, no API key.

## Optional

| Tool | Version used | Needed for | Install |
|---|---|---|---|
| A web browser with internet | any current | the diagrams in the `.html` reports (Mermaid 10.9.1 is loaded from the jsDelivr CDN) | n/a |
| Docker + Compose | 29.9.2 | the full stack (MongoDB, backend, frontend) | system package |
| MongoDB 7 | via Docker `mongo:7.0` | server mode and the opt-in database test | `docker compose up -d mongodb` |
| Node.js + npm | 22.22.2 | the React dashboard (`frontend/`) | system package, then `cd frontend && npm install && npm run dev` |
| Langfuse (self-hosted) | `langfuse/langfuse:2`, Python package `langfuse` 2.60 | seeing every prompt and answer in a UI (the flow log already records them) | `docker compose -f docker-compose.yml -f docker-compose.langfuse.yml up -d`, then keys in `.env` |
| Nemotron API key | n/a | `--llm` mode | NVIDIA API catalogue; put in `.env` |
| GitHub token | n/a | the GitHub Actions monitor | GitHub settings; put in `.env` |

## Dashboard checks (optional)

```bash
cd frontend && npm install
npx tsc --noEmit         # type-check
npx vite build           # production build (dist/ is git-ignored)
```

The Flow tab was also checked by rendering its React components on the server with real API output (`react-dom/server` through Vite's `ssrLoadModule`) and taking a headless Google Chrome screenshot (`google-chrome --headless=new --screenshot=...`). Neither is required to use the project.

## Used only to verify the diagrams (not part of the project)

The Mermaid syntax of all 30 diagrams in the README and `docs/showcase/` was checked with the real Mermaid parser:

```bash
mkdir /tmp/mm && cd /tmp/mm && npm init -y && npm i mermaid@10.9.1 jsdom@24
# then call mermaid.parse() on every ```mermaid block, with jsdom providing window/document
```

Result: 30 diagrams checked (README and `docs/showcase/`), 0 invalid. This is not needed to use the project.

## Environment notes found while setting up

- The checked-in `.venv/` was empty (no packages). It was recreated with Python 3.12.
- `pytest-asyncio==0.23.3` failed test collection with pytest 8.2.2; it is now pinned to 0.23.8.
- `.env` contained settings from another machine (`DATA_DIR=/home/neil/...`). `Settings` now falls back to `<repo>/data` with a warning if `DATA_DIR` does not exist.
- A test run used to connect to the MongoDB in `.env` and write and delete a record. It is now opt-in (`AGENTOPS_TEST_MONGO=1`).
- `.env` holds live credentials (database password, tokens). Do not commit or share it; rotate them if they were ever exposed (see `decisions.md`).

## Verify the installation

```bash
.venv/bin/python -m pytest -q                         # 138 passed, 1 skipped
.venv/bin/python scripts/investigate.py run shoplite-S2
.venv/bin/python scripts/investigate.py showcase      # rebuilds docs/showcase/
```
