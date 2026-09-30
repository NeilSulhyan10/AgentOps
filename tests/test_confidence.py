import pytest
from backend.models import AgentType
from backend.orchestrator.confidence import (
    calculate_overall_confidence,
    is_confidence_sufficient,
    get_confidence_level
)


def test_calculate_overall_confidence_multiple():
    confidences = {
        AgentType.CICD: 0.8,
        AgentType.KUBERNETES: 0.9,
        AgentType.OBSERVABILITY: 0.7
    }
    overall = calculate_overall_confidence(confidences)
    expected = 1 - (1-0.8) * (1-0.9) * (1-0.7)
    assert abs(overall - expected) < 0.001


def test_calculate_overall_confidence_two_agents():
    confidences = {
        AgentType.CICD: 0.85,
        AgentType.KUBERNETES: 0.92
    }
    overall = calculate_overall_confidence(confidences)
    expected = 1 - (1-0.85) * (1-0.92)
    assert abs(overall - expected) < 0.001


def test_calculate_overall_confidence_single():
    confidences = {AgentType.CICD: 0.8}
    overall = calculate_overall_confidence(confidences)
    assert overall == 0.8


def test_calculate_overall_confidence_empty():
    overall = calculate_overall_confidence({})
    assert overall == 0.0


def test_calculate_overall_confidence_zero():
    confidences = {AgentType.CICD: 0.0, AgentType.KUBERNETES: 0.0}
    overall = calculate_overall_confidence(confidences)
    assert overall == 0.0


def test_calculate_overall_confidence_high():
    confidences = {AgentType.CICD: 0.95, AgentType.KUBERNETES: 0.98}
    overall = calculate_overall_confidence(confidences)
    assert overall > 0.99


def test_is_confidence_sufficient_above_threshold():
    assert is_confidence_sufficient(0.8, 0.75) is True
    assert is_confidence_sufficient(0.75, 0.75) is True
    assert is_confidence_sufficient(0.99, 0.75) is True


def test_is_confidence_sufficient_below_threshold():
    assert is_confidence_sufficient(0.7, 0.75) is False
    assert is_confidence_sufficient(0.5, 0.75) is False
    assert is_confidence_sufficient(0.0, 0.75) is False


def test_get_confidence_level():
    assert get_confidence_level(0.95) == "very_high"
    assert get_confidence_level(0.85) == "high"
    assert get_confidence_level(0.6) == "medium"
    assert get_confidence_level(0.3) == "low"
    assert get_confidence_level(0.1) == "very_low"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])