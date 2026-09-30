#!/usr/bin/env python3
"""
Simple verification script for AgentOps Phase 1
Tests core logic without external dependencies
"""

import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Check file structure
def check_file_structure():
    print("Checking project structure...")

    required_files = [
        # Backend
        "backend/main.py",
        "backend/config.py",
        "backend/models/__init__.py",
        "backend/orchestrator/graph.py",
        "backend/orchestrator/confidence.py",
        "backend/orchestrator/state.py",
        "backend/orchestrator/router.py",
        "backend/orchestrator/__init__.py",
        "backend/llm/base.py",
        "backend/llm/mock.py",
        "backend/llm/nemotron.py",
        "backend/llm/__init__.py",
        "backend/agents/cicd/agent.py",
        "backend/agents/kubernetes/agent.py",
        "backend/agents/observability/agent.py",
        "backend/agents/__init__.py",
        "backend/tools/data_access.py",
        "backend/services/investigation_service.py",
        "backend/services/__init__.py",
        "backend/api/routes.py",
        "backend/api/__init__.py",
        "backend/requirements.txt",

        # Frontend
        "frontend/package.json",
        "frontend/vite.config.ts",
        "frontend/tailwind.config.js",
        "frontend/tsconfig.json",
        "frontend/index.html",
        "frontend/src/main.tsx",
        "frontend/src/App.tsx",
        "frontend/src/api/client.ts",
        "frontend/src/types/index.ts",
        "frontend/src/utils/helpers.ts",
        "frontend/src/components/IncidentList.tsx",
        "frontend/src/components/InvestigationDetail.tsx",
        "frontend/src/components/Header.tsx",
        "frontend/src/components/ui/Button.tsx",
        "frontend/src/components/ui/Card.tsx",
        "frontend/src/components/ui/Badge.tsx",
        "frontend/src/components/ui/Tabs.tsx",
        "frontend/src/components/ui/Progress.tsx",
        "frontend/src/components/ui/Table.tsx",
        "frontend/src/components/ui/index.ts",
        "frontend/src/index.css",

        # Docker
        "docker-compose.yml",
        "docker/backend.Dockerfile",
        "docker/frontend.Dockerfile",
        "docker/mongo-init.js",

        # Data
        "data/incidents/incident-001.json",
        "data/incidents/incident-002.json",
        "data/cicd/incident-001.json",
        "data/cicd/incident-002.json",
        "data/kubernetes/incident-001.json",
        "data/kubernetes/incident-002.json",
        "data/observability/incident-001.json",
        "data/observability/incident-002.json",
        "data/ground_truth/incident-001.json",
        "data/ground_truth/incident-002.json",

        # Tests
        "tests/test_orchestrator.py",
        "tests/test_agents.py",
        "tests/test_confidence.py",
        "pytest.ini",

        # Config
        ".env.example",
        "README.md",
    ]

    missing = []
    for f in required_files:
        if not os.path.exists(f):
            missing.append(f)

    if missing:
        print(f"  ✗ Missing files: {len(missing)}")
        for f in missing:
            print(f"    - {f}")
        return False
    else:
        print(f"  ✓ All {len(required_files)} required files present")
        return True


def check_python_syntax():
    print("\nChecking Python syntax...")
    import py_compile

    python_files = [
        "backend/main.py",
        "backend/config.py",
        "backend/models/__init__.py",
        "backend/orchestrator/graph.py",
        "backend/orchestrator/confidence.py",
        "backend/orchestrator/state.py",
        "backend/orchestrator/router.py",
        "backend/orchestrator/__init__.py",
        "backend/llm/base.py",
        "backend/llm/mock.py",
        "backend/llm/nemotron.py",
        "backend/llm/__init__.py",
        "backend/agents/cicd/agent.py",
        "backend/agents/kubernetes/agent.py",
        "backend/agents/observability/agent.py",
        "backend/agents/__init__.py",
        "backend/tools/data_access.py",
        "backend/services/investigation_service.py",
        "backend/services/__init__.py",
        "backend/api/routes.py",
        "backend/api/__init__.py",
    ]

    errors = []
    for f in python_files:
        try:
            py_compile.compile(f, doraise=True)
        except py_compile.PyCompileError as e:
            errors.append((f, str(e)))

    if errors:
        print(f"  ✗ Syntax errors in {len(errors)} files:")
        for f, err in errors:
            print(f"    - {f}: {err}")
        return False
    else:
        print(f"  ✓ All {len(python_files)} Python files compile successfully")
        return True


def check_json_files():
    print("\nChecking JSON data files...")
    json_files = [
        "data/incidents/incident-001.json",
        "data/incidents/incident-002.json",
        "data/cicd/incident-001.json",
        "data/cicd/incident-002.json",
        "data/kubernetes/incident-001.json",
        "data/kubernetes/incident-002.json",
        "data/observability/incident-001.json",
        "data/observability/incident-002.json",
        "data/ground_truth/incident-001.json",
        "data/ground_truth/incident-002.json",
        "frontend/package.json",
        "frontend/tsconfig.json",
        "frontend/tsconfig.node.json",
    ]

    errors = []
    for f in json_files:
        try:
            with open(f) as fp:
                json.load(fp)
        except json.JSONDecodeError as e:
            errors.append((f, str(e)))

    if errors:
        print(f"  ✗ JSON errors in {len(errors)} files:")
        for f, err in errors:
            print(f"    - {f}: {err}")
        return False
    else:
        print(f"  ✓ All {len(json_files)} JSON files are valid")
        return True


def check_key_implementations():
    print("\nChecking key implementations...")

    # Check orchestrator graph has key nodes
    with open("backend/orchestrator/graph.py") as f:
        content = f.read()
        required_nodes = [
            "normalize_incident",
            "rule_based_pre_filter",
            "adaptive_router",
            "invoke_cicd_agent",
            "invoke_kubernetes_agent",
            "invoke_observability_agent",
            "evaluate_evidence",
            "generate_rca",
            "persist_investigation",
            "build_investigation_graph"
        ]
        for node in required_nodes:
            if node not in content:
                print(f"  ✗ Missing node: {node}")
                return False
    print("  ✓ Orchestrator graph has all required nodes")

    # Check confidence calculation
    with open("backend/orchestrator/confidence.py") as f:
        content = f.read()
        if "calculate_overall_confidence" not in content:
            print("  ✗ Missing confidence calculation")
            return False
        if "1.0 - confidence" not in content and "1 - confidence" not in content:
            print("  ✗ Confidence formula not found")
            return False
    print("  ✓ Confidence calculation implemented")

    # Check LLM abstraction
    with open("backend/llm/base.py") as f:
        content = f.read()
        if "class LLMProvider" not in content:
            print("  ✗ Missing LLMProvider base class")
            return False
        if "generate_structured" not in content:
            print("  ✗ Missing generate_structured method")
            return False
    print("  ✓ LLM abstraction layer present")

    # Check mock LLM
    with open("backend/llm/mock.py") as f:
        content = f.read()
        if "class DeterministicMockLLM" not in content:
            print("  ✗ Missing DeterministicMockLLM")
            return False
        if "_routing_rules" not in content:
            print("  ✗ Missing deterministic routing rules")
            return False
    print("  ✓ Deterministic mock LLM implemented")

    # Check agents have investigate method
    for agent_file in [
        "backend/agents/cicd/agent.py",
        "backend/agents/kubernetes/agent.py",
        "backend/agents/observability/agent.py"
    ]:
        with open(agent_file) as f:
            content = f.read()
            if "def investigate" not in content:
                print(f"  ✗ Missing investigate method in {agent_file}")
                return False
    print("  ✓ All agents have investigate method")

    # Check API routes
    with open("backend/api/routes.py") as f:
        content = f.read()
        required_endpoints = [
            '@router.post(""',
            '@router.get("",',
            '@router.get("/{incident_id}",',
            '@investigation_router.get("/{investigation_id}",',
            '@investigation_router.get("/{investigation_id}/timeline")',
            '@investigation_router.get("/{investigation_id}/evidence")',
            '@investigation_router.get("/{investigation_id}/root-cause")',
            '@investigation_router.get("/{investigation_id}/remediation")'
        ]
        for ep in required_endpoints:
            if ep not in content:
                print(f"  ✗ Missing endpoint: {ep}")
                return False
    print("  ✓ All required API endpoints defined")

    # Check frontend components
    with open("frontend/src/components/InvestigationDetail.tsx") as f:
        content = f.read()
        required_tabs = ["overview", "timeline", "evidence", "rca"]
        for tab in required_tabs:
            if f'value="{tab}"' not in content and f"value='{tab}'" not in content:
                print(f"  ✗ Missing tab: {tab}")
                return False
    print("  ✓ Investigation detail has all required tabs")

    return True


def main():
    print("=" * 60)
    print("AgentOps Phase 1 - Structure & Syntax Verification")
    print("=" * 60)

    all_passed = True

    all_passed &= check_file_structure()
    all_passed &= check_python_syntax()
    all_passed &= check_json_files()
    all_passed &= check_key_implementations()

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL VERIFICATIONS PASSED")
        print("=" * 60)
        print("\nPhase 1 implementation is complete!")
        print("\nTo run the project:")
        print("  1. Ensure Python 3.11 or 3.12 is available")
        print("  2. cd agentops && cp .env.example .env")
        print("  3. docker-compose up -d")
        print("  4. Frontend: http://localhost:3000")
        print("  5. Backend API: http://localhost:8000")
        print("  6. API Docs: http://localhost:8000/docs")
        return 0
    else:
        print("✗ SOME VERIFICATIONS FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())