"""Tests for the critic/verifier agent, the new specialists and the scenario catalogue."""

import json

import pytest

from backend.models import (
    AgentFinding,
    CriticReview,
    Evidence,
    EvidenceType,
    HypothesisType,
    InvestigationStatus,
)
from backend.orchestrator.critic import deterministic_review
from backend.orchestrator.graph import build_investigation_graph, create_initial_state
from backend.orchestrator.router import select_next_agent
from backend.runtime.agent_loader import RESERVED_AGENT_NAMES, get_specialist_agent_names
from backend.services.scenarios import list_scenarios, load_scenario_incident
from backend.tools.data_access import data_loader


def _evidence(n=2):
    return [
        Evidence(investigation_id="i", agent_type="cicd_analyzer", evidence_type=EvidenceType.DEPLOYMENT,
                 description=f"deploy {k}", raw_data={}, confidence=0.8, source="t")
        for k in range(n)
    ]


def _finding(agent, hypothesis, evidence, confidence=0.9):
    return AgentFinding(investigation_id="i", agent_type=agent, hypothesis=hypothesis, finding="f",
                        evidence=[e.evidence_id for e in evidence], confidence=confidence)


class TestDeterministicReview:
    def test_ungrounded_findings_are_challenged(self):
        ev = _evidence()
        f = AgentFinding(investigation_id="i", agent_type="cicd_analyzer",
                         hypothesis=HypothesisType.DEPLOYMENT_INDUCED_FAILURE, finding="f",
                         evidence=["nope"], confidence=0.9)
        review = deterministic_review([f], ev, ["kubernetes_analyzer"], 1)
        assert review.verdict == "challenged"
        assert review.suggested_agent == "kubernetes_analyzer"

    def test_single_layer_is_challenged_while_specialists_remain(self):
        ev = _evidence()
        f = _finding("cicd_analyzer", HypothesisType.DEPLOYMENT_INDUCED_FAILURE, ev)
        review = deterministic_review([f], ev, ["kubernetes_analyzer", "observability_analyzer"], 1)
        assert review.verdict == "challenged"
        assert review.suggested_agent == "kubernetes_analyzer"

    def test_single_layer_is_confirmed_when_nothing_left_to_ask(self):
        ev = _evidence()
        f = _finding("cicd_analyzer", HypothesisType.DEPLOYMENT_INDUCED_FAILURE, ev)
        review = deterministic_review([f], ev, [], 1)
        assert review.verdict == "confirmed"
        assert review.concerns  # caveat is kept

    def test_complementary_layers_are_confirmed(self):
        ev = _evidence()
        findings = [
            _finding("cicd_analyzer", HypothesisType.DEPLOYMENT_INDUCED_FAILURE, ev, 0.85),
            _finding("kubernetes_analyzer", HypothesisType.KUBERNETES_OOM, ev, 0.9),
        ]
        review = deterministic_review(findings, ev, ["observability_analyzer"], 1)
        assert review.verdict == "confirmed"
        assert not review.concerns

    def test_unreconciled_contradiction_is_challenged(self):
        ev = _evidence()
        findings = [
            _finding("kubernetes_analyzer", HypothesisType.KUBERNETES_OOM, ev, 0.9),
            _finding("traffic_analyzer", HypothesisType.TRAFFIC_INCIDENT, ev, 0.8),
        ]
        review = deterministic_review(findings, ev, ["observability_analyzer"], 1)
        assert review.verdict == "challenged"


class TestRouterHonoursCritic:
    def test_challenge_overrides_gap_mapping(self):
        state = create_initial_state(load_scenario_incident("incident-001"))
        state.evidence_gaps = ["deployment_details"]
        state.critic_reviews.append(CriticReview(
            verdict="challenged", suggested_agent="observability_analyzer", confidence=0.5))
        agent, reason = select_next_agent(state, ["cicd_analyzer", "observability_analyzer"])
        assert agent == "observability_analyzer"
        assert "Critic" in reason


class TestAgentDiscovery:
    def test_critic_is_reserved_not_dispatchable(self):
        assert "critic" in RESERVED_AGENT_NAMES
        assert "critic" not in get_specialist_agent_names()

    def test_new_specialists_discovered(self):
        names = get_specialist_agent_names()
        for expected in ("config_analyzer", "dependency_analyzer", "traffic_analyzer"):
            assert expected in names


class TestScenarios:
    def test_every_scenario_has_all_fixture_layers_and_ground_truth(self):
        scenarios = list_scenarios()
        assert len(scenarios) >= 7
        for s in scenarios:
            sid = s["scenario_id"]
            assert load_scenario_incident(sid).incident_id == sid
            assert data_loader.load_kubernetes_data(sid)
            assert data_loader.load_observability_data(sid)
            truth = (data_loader.data_dir / "ground_truth" / f"{sid}.json")
            assert json.loads(truth.read_text())["root_cause_type"]

    def test_unknown_scenario_raises(self):
        with pytest.raises(KeyError):
            load_scenario_incident("does-not-exist")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("sid", ["incident-003", "incident-004", "incident-005", "incident-006", "incident-007"])
    async def test_generated_scenario_runs_through_graph_with_critic(self, sid):
        graph = build_investigation_graph()
        state = create_initial_state(load_scenario_incident(sid), max_iterations=5)
        result = await graph.ainvoke({
            "investigation": state, "messages": [], "current_agent": None,
            "should_continue": True, "next_action": "",
        })
        inv = result["investigation"]
        assert inv.root_cause is not None
        assert inv.critic_reviews, "critic must review before the RCA"
        assert inv.investigation_status in (InvestigationStatus.COMPLETED, InvestigationStatus.MAX_ITERATIONS_REACHED)
        assert len(inv.critic_reviews) <= 2  # bounded by critic_max_rounds
