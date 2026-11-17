"""Flow inspection: events -> trace -> diagrams, and real runs with injected faults."""

import itertools

import pytest

from backend.config import settings
from backend.faults import FAULTS
from backend.flow import build_trace, group_by_investigation, read_events
from backend.flow.diagram import PIPELINE_EDGES, PIPELINE_NODES, app_map, pipeline_map
from backend.flow.layers import AFFECTED, NOT_CHECKED, ROOT, layer_statuses
from backend.flow.report import to_html, to_markdown, to_text
from backend.flow.trace import ERROR, OK, WARNING
from backend.llm import reset_llm_provider
from backend.orchestrator import build_investigation_graph, create_initial_state, run_investigation
from backend.services.scenarios import load_scenario_incident


_clock = itertools.count()


def _event(name, **fields):
    """A flow-log event; timestamps increase in creation order."""
    return {"ts": f"2026-01-01T00:00:00.{next(_clock):06d}", "investigation_id": "inv-1", "event": name, **fields}


CLEAN_RUN = [
    _event("investigation_started", incident_id="demo", title="Pods OOMKilled", service_name="shop", engine="rules"),
    _event("pre_filter", hypothesis="kubernetes_oom", evidence_gaps=["pod_memory_status"]),
    _event("load_evidence", total_evidence=9, sources=["kubernetes_fixture"]),
    _event("route", iteration=1, selected_agent="kubernetes_analyzer", llm_choice="", used_deterministic_fallback=False, reasoning="oom"),
    _event("agent_finding", agent="kubernetes_analyzer", hypothesis="kubernetes_oom", confidence=0.9, grounded_evidence=3, cited_evidence=3, finding="OOM"),
    _event("evaluate", overall_confidence=0.9, threshold=0.75, is_sufficient=True),
    _event("critic", round=1, verdict="confirmed", confidence=0.9, concerns=[], looping_back=False),
    _event("rca", status="completed", root_cause_type="kubernetes_oom", overall_confidence=0.9, agents_invoked=["kubernetes_analyzer"]),
    _event("investigation_finished", status="completed"),
]


class TestTrace:
    def test_clean_run_has_no_problems(self):
        trace = build_trace(CLEAN_RUN)
        assert trace.worst_status == OK
        assert trace.problems == []
        assert trace.root_cause_type == "kubernetes_oom"
        assert [s.node for s in trace.steps] == [
            "normalize", "pre_filter", "load_evidence", "route", "invoke_agent",
            "evaluate", "critique", "generate_rca", "persist",
        ]

    def test_unusable_llm_answer_marks_the_step_that_used_the_fallback(self):
        events = CLEAN_RUN[:3] + [_event("llm_parse_fallback", task="routing", error="not json")] + CLEAN_RUN[3:]
        trace = build_trace(events)
        assert [s.node for s in trace.problems] == ["route"]
        assert trace.problems[0].status == WARNING

    def test_ungrounded_finding_is_a_warning(self):
        events = list(CLEAN_RUN)
        events[4] = _event("agent_finding", agent="kubernetes_analyzer", hypothesis="kubernetes_oom",
                           confidence=0.9, grounded_evidence=0, cited_evidence=2, finding="OOM")
        trace = build_trace(events)
        assert [s.node for s in trace.problems] == ["invoke_agent"]

    def test_failed_node_is_the_only_error(self):
        events = CLEAN_RUN[:4] + [
            _event("node_failed", node="invoke_agent", agent="kubernetes_analyzer", error="RuntimeError('boom')"),
            _event("investigation_finished", status="failed"),
        ]
        trace = build_trace(events)
        assert trace.worst_status == ERROR
        assert [(s.node, s.status) for s in trace.problems] == [("invoke_agent", ERROR)]
        assert "FAILED at node 'invoke_agent'" in to_text(trace)

    def test_critic_challenge_that_loops_back_is_normal_but_unresolved_one_is_not(self):
        looping = build_trace(CLEAN_RUN[:6] + [_event("critic", round=1, verdict="challenged", confidence=0.6,
                                                       concerns=["single layer"], looping_back=True, suggested_agent="cicd_analyzer")])
        stuck = build_trace(CLEAN_RUN[:6] + [_event("critic", round=2, verdict="challenged", confidence=0.3,
                                                     concerns=["still single layer"], looping_back=False)])
        assert looping.problems == []
        assert [s.node for s in stuck.problems] == ["critique"]

    def test_events_are_grouped_per_investigation(self):
        other = [{**e, "investigation_id": "inv-2"} for e in CLEAN_RUN]
        runs = group_by_investigation(CLEAN_RUN + other)
        assert set(runs) == {"inv-1", "inv-2"}
        assert len(runs["inv-1"]) == len(CLEAN_RUN)


class TestDiagrams:
    def test_pipeline_map_mirrors_the_real_graph(self):
        """If someone adds a node or edge to the graph, the diagram must be updated too."""
        real = build_investigation_graph().get_graph()
        real_edges = {(e.source, e.target) for e in real.edges if "__" not in e.source + e.target}
        assert real_edges == set(PIPELINE_EDGES)
        assert {n for n in real.nodes if "__" not in n} == set(PIPELINE_NODES)

    def test_root_cause_layer_is_red(self):
        trace = build_trace(CLEAN_RUN)
        statuses = layer_statuses(trace)
        assert statuses["kubernetes"].status == ROOT
        assert statuses["cicd"].status == NOT_CHECKED
        assert 'kubernetes["' in app_map(trace) and ":::error" in app_map(trace)

    def test_multi_layer_failure_marks_every_layer_with_findings(self):
        events = list(CLEAN_RUN)
        events[7] = _event("rca", status="completed", root_cause_type="multi_layer_failure",
                           overall_confidence=0.8, agents_invoked=["kubernetes_analyzer"])
        assert layer_statuses(build_trace(events))["kubernetes"].status == ROOT

    def test_failed_node_is_red_in_pipeline_map(self):
        events = CLEAN_RUN[:4] + [_event("node_failed", node="invoke_agent", error="boom")]
        diagram = pipeline_map(build_trace(events))
        assert "invoke_agent[" in diagram
        assert [line for line in diagram.splitlines() if line.strip().startswith("invoke_agent[")][0].endswith(":::error")
        assert [line for line in diagram.splitlines() if line.strip().startswith("critique[")][0].endswith(":::skipped")

    def test_reports_render(self):
        trace = build_trace(CLEAN_RUN)
        assert "```mermaid" in to_markdown(trace)
        assert "<html" in to_html(trace) and "kubernetes_oom" in to_html(trace)


@pytest.fixture
def offline(monkeypatch):
    """Rule-based mode with a temp flow log is set up for every test by tests/conftest.py."""
    return monkeypatch


async def _run(scenario_id: str):
    state = await run_investigation(create_initial_state(load_scenario_incident(scenario_id)))
    return state, build_trace(read_events(state.investigation_id))


class TestRealRuns:
    async def test_oom_scenario_points_at_kubernetes(self, offline):
        state, trace = await _run("shoplite-S2")
        assert state.investigation_status == "completed"
        assert state.root_cause.root_cause_type == "kubernetes_oom"
        assert layer_statuses(trace)["kubernetes"].status == ROOT
        assert trace.worst_status != ERROR

    async def test_agent_crash_is_located_at_invoke_agent(self, offline):
        offline.setattr(settings, "fault_injection", "agent_crash")
        reset_llm_provider()
        state, trace = await _run("shoplite-S2")
        assert state.investigation_status == "failed"
        assert [(s.node, s.status) for s in trace.problems if s.status == ERROR] == [("invoke_agent", ERROR)]

    async def test_router_unknown_agent_is_a_warning_at_route(self, offline):
        offline.setattr(settings, "fault_injection", "router_unknown_agent")
        reset_llm_provider()
        state, trace = await _run("shoplite-S2")
        assert state.investigation_status != "failed"
        assert "route" in {s.node for s in trace.problems}

    @pytest.mark.parametrize("fault", sorted(FAULTS))
    async def test_every_fault_leaves_a_visible_problem(self, offline, fault):
        offline.setattr(settings, "fault_injection", fault)
        reset_llm_provider()
        _, trace = await _run("shoplite-S2")
        assert trace.problems, f"fault '{fault}' left no trace in the flow report"
        assert trace.final_status != "running"

    async def test_affected_layers_are_not_called_root(self, offline):
        _, trace = await _run("shoplite-S2")
        statuses = layer_statuses(trace)
        roots = [k for k, s in statuses.items() if s.status == ROOT]
        assert roots == ["kubernetes"]
        assert all(s.status in (AFFECTED, NOT_CHECKED, "clear") for k, s in statuses.items() if k != "kubernetes")
