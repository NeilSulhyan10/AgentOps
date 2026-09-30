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
        started_at=datetime.utcnow(),
        detected_at=datetime.utcnow()
    )


@pytest.fixture
def investigation_state(sample_incident):
    return create_initial_state(sample_incident, max_iterations=5)


def test_create_initial_state(investigation_state, sample_incident):
    assert investigation_state.incident_id == sample_incident.incident_id
    assert investigation_state.investigation_status == InvestigationStatus.PENDING
    assert investigation_state.max_iterations == 5
    assert investigation_state.iteration_count == 0
    assert len(investigation_state.agents_invoked) == 0
    assert investigation_state.overall_confidence == 0.0


def test_calculate_overall_confidence():
    confidences = {
        AgentType.CICD: 0.8,
        AgentType.KUBERNETES: 0.9,
        AgentType.OBSERVABILITY: 0.7
    }
    overall = calculate_overall_confidence(confidences)
    expected = 1 - (1-0.8) * (1-0.9) * (1-0.7)
    assert abs(overall - expected) < 0.001
    assert overall > 0.95


def test_calculate_overall_confidence_empty():
    overall = calculate_overall_confidence({})
    assert overall == 0.0


def test_calculate_overall_confidence_single():
    overall = calculate_overall_confidence({AgentType.CICD: 0.8})
    assert overall == 0.8


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
async def test_investigation_graph(sample_incident):
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

    investigation_state.agent_findings = [
        AgentFinding(
            investigation_id=investigation_state.investigation_id,
            agent_type=AgentType.CICD,
            hypothesis=HypothesisType.DEPLOYMENT_INDUCED_FAILURE,
            finding="Recent deployment changed memory limit",
            evidence=["deployment_timestamp_match", "config_change_detected"],
            confidence=0.85,
            reasoning="Deployment occurred 2 minutes before incident",
            iteration=1
        ),
        AgentFinding(
            investigation_id=investigation_state.investigation_id,
            agent_type=AgentType.KUBERNETES,
            hypothesis=HypothesisType.KUBERNETES_OOM,
            finding="Pod OOMKilled with exit code 137",
            evidence=["exit_code_137", "memory_usage_980Mi", "memory_limit_1Gi"],
            confidence=0.92,
            reasoning="Memory usage exceeded limit",
            iteration=2
        )
    ]
    investigation_state.agents_invoked = [AgentType.CICD, AgentType.KUBERNETES]
    investigation_state.confidence_scores = {
        AgentType.CICD: 0.85,
        AgentType.KUBERNETES: 0.92
    }
    investigation_state.overall_confidence = calculate_overall_confidence(
        investigation_state.confidence_scores
    )

    rca = synthesize_rca(investigation_state)

    assert rca.investigation_id == investigation_state.investigation_id
    assert rca.root_cause_type == HypothesisType.KUBERNETES_OOM
    assert len(rca.contributing_factors) == 2
    assert rca.overall_confidence > 0.9
    assert len(rca.agents_consulted) == 2


def test_generate_remediation():
    from backend.models import RootCauseAnalysis

    rca = RootCauseAnalysis(
        investigation_id="test-001",
        incident_id="incident-001",
        root_cause="Memory limit reduced causing OOM",
        root_cause_type=HypothesisType.KUBERNETES_OOM,
        contributing_factors=["Memory limit reduced", "High memory usage"],
        evidence=["exit_code_137", "memory_limit_changed"],
        agents_consulted=[AgentType.KUBERNETES],
        overall_confidence=0.9
    )

    remediation = generate_remediation(rca)

    assert remediation.investigation_id == rca.investigation_id
    assert remediation.rca_id == rca.rca_id
    assert "memory" in remediation.recommendation.lower()
    assert len(remediation.steps) > 0
    assert remediation.priority == "high"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])