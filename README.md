# AgentOps: Adaptive Multi-Agent Intelligence for DevOps

An end-to-end adaptive multi-agent DevOps incident investigation and Root Cause Analysis (RCA) system.

## Team
- Neil Sulhyan
- Huma Naaz Mohammad
- Dhriti Shah

## Architecture Overview

```
agentops/
├── backend/                 # Python 3.11 + FastAPI
│   ├── api/                 # REST API endpoints
│   ├── agents/              # Specialist agents
│   │   ├── cicd/           # CI/CD incident investigation
│   │   ├── kubernetes/     # Kubernetes incident investigation
│   │   └── observability/  # Observability incident investigation
│   ├── orchestrator/       # LangGraph-based adaptive orchestration
│   │   ├── graph.py        # Investigation flow graph
│   │   ├── router.py       # Adaptive agent routing
│   │   ├── state.py        # Investigation state schema
│   │   └── confidence.py   # Confidence calculation
│   ├── llm/                # LLM abstraction layer
│   │   ├── base.py         # Base LLM provider interface
│   │   ├── mock.py         # Mock LLM for development
│   │   └── nemotron.py     # Nemotron 3 Ultra integration (Phase 13)
│   ├── tools/              # Agent tools for data access
│   ├── models/             # Pydantic models
│   ├── services/           # Business logic services
│   └── main.py             # FastAPI application entry
├── frontend/               # React + Tailwind CSS
├── data/                   # Simulated telemetry fixtures
├── evaluation/             # Evaluation framework
├── tests/                  # Unit and integration tests
├── docker/                 # Docker configurations
├── docs/                   # Documentation
├── docker-compose.yml      # Local development stack
├── .env.example            # Environment variables template
└── README.md               # This file
```

## Quick Start

```bash
# Copy environment template
cp .env.example .env

# Start all services
docker-compose up -d

# Access services
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
# MongoDB: localhost:27017
```

## Development Phases

1. **Phase 1** - Project Foundation (this phase)
2. **Phase 2** - Simulated DevOps Environment
3. **Phase 3** - Specialist Agents
4. **Phase 4** - Investigation State
5. **Phase 5** - Adaptive Orchestrator
6. **Phase 6** - Confidence System
7. **Phase 7** - RCA + Remediation
8. **Phase 8** - FastAPI Endpoints
9. **Phase 9** - MongoDB Persistence
10. **Phase 10** - Dashboard
11. **Phase 11** - Evaluation
12. **Phase 12** - Testing
13. **Phase 13** - LLM Integration (Final)
14. **Phase 14** - Dockerization
15. **Phase 15** - Final Demonstration

## LLM Integration Policy

**The real LLM (Nemotron 3 Ultra) is integrated ONLY in Phase 13.**

All prior phases use deterministic, rule-based logic with a mock LLM provider.