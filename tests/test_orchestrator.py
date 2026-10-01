# Set required GitHub environment variables BEFORE importing backend modules
import os
os.environ["GITHUB_TOKEN"] = "test-token"
os.environ["GITHUB_OWNER"] = "test-owner"
os.environ["GITHUB_REPO"] = "test-repo"
os.environ["GITHUB_BRANCH"] = "main"
os.environ["GITHUB_TIME_WINDOW_HOURS"] = "24"

import pytest
import asyncio
from datetime import datetime
from backend.models import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    AgentType,
    HypothesisType,
    InvestigationStatus
)
from backend.orchestrator import (
    build_investigation_graph,
    create_initial_state,
    calculate_overall_confidence,
    synthesize_rca,
    generate_remediation
)
from backend.orchestrator.state import state_manager


@pytest.fixture
def sample_incident():
    return Incident(
        incident_id="test-incident-001",
        title="Test Incident",
        description="Test deployment caused memory issue",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        source="test",
        service_name="test-service",
        namespace="production",
        started_at="2024-01-15T10:30:00Z",
        detected_at="2024-01-15T10:30:00Z",
    )


@pytest.fixture
def investigation_state(sample_incident):
    return create_initial_state(sample_incident, max_iterations=3)


@pytest.mark.asyncio
async def test_create_initial_state(sample_incident):
    state = create_initial_state(sample_incident, max_iterations=5)
    assert state.incident_id == sample_incident.incident_id
    assert state.incident == sample_incident
    assert state.max_iterations == 5
    assert state.investigation_status == InvestigationStatus.PENDING


@pytest.mark.asyncio
async def test_calculate_overall_confidence():
    from backend.orchestrator.confidence import calculate_overall_confidence
    from backend.models import AgentType
    
    confidence = calculate_overall_confidence({AgentType.CICD: 0.9, AgentType.KUBERNETES: 0.85})
    assert 0.9 <= confidence <= 1.0
    
    confidence = calculate_overall_confidence({AgentType.CICD: 0.5})
    assert confidence == 0.5
    
    confidence = calculate_overall_confidence({})
    assert confidence == 0.0


@pytest.mark.asyncio
async def test_calculate_overall_confidence_empty():
    from backend.orchestrator.confidence import calculate_overall_confidence
    assert calculate_overall_confidence({}) == 0.0


@pytest.mark.asyncio
async def test_calculate_overall_confidence_single():
    from backend.orchestrator.confidence import calculate_overall_confidence
    from backend.models import AgentType
    assert calculate_overall_confidence({"cicd": 0.9}) == 0.9


@pytest.mark.asyncio
async def test_state_manager(investigation_state):
    from backend.services.mongodb import mongodb
    from backend.models.mongodb import IncidentDoc, InvestigationDoc
    await mongodb.connect()
    try:
        # Clean up any existing test data
        await IncidentDoc.find({"incident_id": "test-incident-001"}).delete()
        await InvestigationDoc.find({"incident_id": "test-incident-001"}).delete()
        
        await state_manager.create_state(investigation_state.incident, investigation_state.max_iterations, investigation_state)
        print(f"Created state with investigation_id: {investigation_state.investigation_id}")
        
        # Debug: check what's in the database
        all_docs = await InvestigationDoc.find_all().to_list()
        print(f"All investigation docs: {len(all_docs)}")
        for doc in all_docs:
            print(f"  Doc: investigation_id={doc.investigation_id}, incident_id={doc.incident_id}, _id={doc.id}")
        
        # Try to find by investigation_id
        doc = await InvestigationDoc.find_one(InvestigationDoc.investigation_id == investigation_state.investigation_id)
        print(f"Direct find_one result: {doc}")
        
        retrieved = await state_manager.get_state(investigation_state.investigation_id)
        print(f"Retrieved state: {retrieved}")
        assert retrieved is not None, f"State not found for investigation_id: {investigation_state.investigation_id}"
        assert retrieved.investigation_id == investigation_state.investigation_id
        await state_manager.delete_state(investigation_state.investigation_id)
    finally:
        await mongodb.close()


@pytest.mark.asyncio
async def test_investigation_graph(sample_incident, monkeypatch):
    # Mock the get_cicd_evidence_from_github function to return mock evidence
    # This avoids making real GitHub API calls during testing
    from backend.models import Evidence, AgentType, EvidenceType
    from datetime import datetime
    
    async def mock_get_cicd_evidence(incident):
        return [
            Evidence(
                investigation_id="",
                agent_type=AgentType.CICD,
                evidence_type=EvidenceType.DEPLOYMENT,
                description="Deployment deploy-12345 at 2024-01-15T10:28:00Z",
                raw_data={"deployment_id": "deploy-12345", "timestamp": "2024-01-15T10:28:00Z"},
                confidence=0.8,
                source="github_actions"
            ),
            Evidence(
                investigation_id="",
                agent_type=AgentType.CICD,
                evidence_type=EvidenceType.CODE_CHANGE,
                description="Code change in config/memory.js: Reduced memory limit from 1Gi to 512Mi",
                raw_data={"file": "config/memory.js", "description": "Reduced memory limit from 1Gi to 512Mi"},
                confidence=0.7,
                source="github_actions"
            ),
            Evidence(
                investigation_id="",
                agent_type=AgentType.CICD,
                evidence_type=EvidenceType.CONFIG_CHANGE,
                description="Config change: resources.limits.memory = 512Mi",
                raw_data={"key": "resources.limits.memory", "old_value": "1Gi", "new_value": "512Mi"},
                confidence=0.85,
                source="github_actions"
            ),
        ]
    
    import backend.tools.data_access as data_access_module
    monkeypatch.setattr(data_access_module, "get_cicd_evidence_from_github", mock_get_cicd_evidence)
    
    from backend.orchestrator import build_investigation_graph, create_initial_state
    from backend.models import InvestigationStatus
    
    graph = build_investigation_graph()
    initial_state = create_initial_state(sample_incident, max_iterations=3)

    graph_input = {
        "investigation": initial_state,
        "messages": [],
        "current_agent": None,
        "should_continue": True,
        "next_action": "normalize"
    }

    result = await graph.ainvoke(graph_input)
    final_state = result["investigation"]

    assert final_state.investigation_status in [
        InvestigationStatus.COMPLETED,
        InvestigationStatus.MAX_ITERATIONS_REACHED,
        InvestigationStatus.INSUFFICIENT_EVIDENCE
    ]
    assert final_state.iteration_count <= 3
    assert final_state.incident_id == sample_incident.incident_id


def test_synthesize_rca(investigation_state):
    from backend.models import AgentFinding, Evidence, EvidenceType
    from backend.orchestrator.confidence import calculate_overall_confidence, synthesize_rca
    
    investigation_state.agent_findings = [
        AgentFinding(
            investigation_id=investigation_state.investigation_id,
            agent_type="cicd",
            hypothesis=HypothesisType.DEPLOYMENT_INDUCED_FAILURE,
            finding="Recent deployment changed memory limit",
            evidence=["deployment_timestamp_match", "config_change_detected"],
            confidence=0.85,
            reasoning="Deployment occurred 2 minutes before incident",
            iteration=1
        ),
        AgentFinding(
            investigation_id=investigation_state.investigation_id,
            agent_type="kubernetes",
            hypothesis=HypothesisType.KUBERNETES_OOM,
            finding="Pod OOMKilled with exit code 137",
            evidence=["exit_code_137", "memory_usage_980Mi", "memory_limit_1Gi"],
            confidence=0.92,
            reasoning="Memory usage exceeded limit",
            iteration=2
        )
    ]
    investigation_state.agents_invoked = ["cicd", "kubernetes"]
    investigation_state.confidence_scores = {
        "cicd": 0.85,
        "kubernetes": 0.92
    }
    investigation_state.overall_confidence = calculate_overall_confidence(
        investigation_state.confidence_scores
    )

    from backend.orchestrator.confidence import synthesize_rca
    rca = synthesize_rca(investigation_state)

    assert rca.investigation_id == investigation_state.investigation_id
    assert rca.root_cause_type == HypothesisType.KUBERNETES_OOM
    assert len(rca.contributing_factors) == 2
    assert rca.overall_confidence > 0.9
    assert len(rca.agents_consulted) == 2


def test_generate_remediation(investigation_state):
    from backend.orchestrator.confidence import generate_remediation
    from backend.models import RootCauseAnalysis, HypothesisType
    
    rca = RootCauseAnalysis(
        investigation_id=investigation_state.investigation_id,
        incident_id=investigation_state.incident_id,
        root_cause="Test root cause",
        root_cause_type=HypothesisType.KUBERNETES_OOM,
        contributing_factors=["factor1", "factor2"],
        overall_confidence=0.9,
    )
    
    remediation = generate_remediation(rca)
    
    assert remediation.investigation_id == investigation_state.investigation_id
    assert remediation.rca_id == rca.rca_id
    assert remediation.priority in ["high", "medium", "low"]
    assert len(remediation.steps) > 0


def test_calculate_overall_confidence():
    from backend.orchestrator.confidence import calculate_overall_confidence
    from backend.models import AgentType
    
    confidence = calculate_overall_confidence({AgentType.CICD: 0.8, AgentType.KUBERNETES: 0.9})
    assert confidence > 0.8
    
    confidence = calculate_overall_confidence({AgentType.CICD: 0.5})
    assert confidence == 0.5
    
    confidence = calculate_overall_confidence({})
    assert confidence == 0.0