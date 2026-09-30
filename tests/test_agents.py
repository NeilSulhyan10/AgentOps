import pytest
from backend.models import Incident, IncidentSeverity, IncidentStatus, AgentType, HypothesisType, Evidence, EvidenceType
from backend.agents.cicd.agent import CICDAgent
from backend.agents.kubernetes.agent import KubernetesAgent
from backend.agents.observability.agent import ObservabilityAgent
from datetime import datetime


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


def test_cicd_agent_no_deployment(sample_incident):
    agent = CICDAgent()
    finding = agent.investigate(sample_incident, [])

    assert finding.agent_type == AgentType.CICD
    assert finding.hypothesis == HypothesisType.UNKNOWN
    assert finding.confidence == 0.1


def test_kubernetes_agent_oom(sample_incident):
    agent = KubernetesAgent()

    evidence = [
        Evidence(
            investigation_id="test",
            agent_type=AgentType.KUBERNETES,
            evidence_type=EvidenceType.POD_EXIT_CODE,
            description="Pod exited with code 137",
            raw_data={"exit_code": 137, "pod": "test-pod"},
            confidence=0.9,
            source="test"
        ),
        Evidence(
            investigation_id="test",
            agent_type=AgentType.KUBERNETES,
            evidence_type=EvidenceType.RESOURCE_USAGE,
            description="Memory usage 980Mi/1Gi",
            raw_data={"usage": "980Mi", "limit": "1Gi", "pod": "test-pod"},
            confidence=0.9,
            source="test"
        )
    ]

    finding = agent.investigate(sample_incident, evidence)

    assert finding.agent_type == AgentType.KUBERNETES
    assert finding.hypothesis == HypothesisType.KUBERNETES_OOM
    assert finding.confidence >= 0.9
    assert "OOMKilled" in finding.finding


def test_kubernetes_agent_high_restarts(sample_incident):
    agent = KubernetesAgent()

    evidence = [
        Evidence(
            investigation_id="test",
            agent_type=AgentType.KUBERNETES,
            evidence_type=EvidenceType.POD_RESTART_COUNT,
            description="Pod restarted 8 times",
            raw_data={"restart_count": 8, "pod": "test-pod"},
            confidence=0.85,
            source="test"
        )
    ]

    finding = agent.investigate(sample_incident, evidence)

    assert finding.agent_type == AgentType.KUBERNETES
    assert finding.hypothesis == HypothesisType.KUBERNETES_OOM
    assert finding.confidence >= 0.8


def test_observability_agent_high_errors(sample_incident):
    agent = ObservabilityAgent()

    evidence = [
        Evidence(
            investigation_id="test",
            agent_type=AgentType.OBSERVABILITY,
            evidence_type=EvidenceType.ERROR_RATE,
            description="Error rate 38%",
            raw_data={"rate": 38.5, "count": 1542},
            confidence=0.9,
            source="test"
        ),
        Evidence(
            investigation_id="test",
            agent_type=AgentType.OBSERVABILITY,
            evidence_type=EvidenceType.LATENCY,
            description="P99 latency 320ms",
            raw_data={"p99": 320, "p95": 180},
            confidence=0.85,
            source="test"
        )
    ]

    finding = agent.investigate(sample_incident, evidence)

    assert finding.agent_type == AgentType.OBSERVABILITY
    assert finding.hypothesis == HypothesisType.TRAFFIC_INCIDENT
    assert finding.confidence >= 0.8


def test_observability_agent_stack_trace(sample_incident):
    agent = ObservabilityAgent()

    evidence = [
        Evidence(
            investigation_id="test",
            agent_type=AgentType.OBSERVABILITY,
            evidence_type=EvidenceType.STACK_TRACE,
            description="NullPointerException in PaymentHandler",
            raw_data={"error": "NullPointerException", "trace": "..."},
            confidence=0.85,
            source="test"
        )
    ]

    finding = agent.investigate(sample_incident, evidence)

    assert finding.agent_type == AgentType.OBSERVABILITY
    assert finding.hypothesis == HypothesisType.APPLICATION_ERROR
    assert finding.confidence >= 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])