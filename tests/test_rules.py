"""The rule-based engine must reach the ground-truth root cause on every ShopLite scenario."""

import json
from pathlib import Path

import pytest

from backend.config import settings
from backend.models import AgentFinding, HypothesisType as H
from backend.orchestrator import create_initial_state, run_investigation
from backend.orchestrator.causal import decide_root_cause, found_nothing
from backend.orchestrator.graph import _without_negated
from backend.services.scenarios import load_scenario_incident

SHOPLITE = [f"shoplite-S{i}" for i in range(1, 8)]


@pytest.mark.parametrize("scenario_id", SHOPLITE)
async def test_rules_match_ground_truth(scenario_id):
    expected = json.loads((Path(settings.data_dir) / "ground_truth" / f"{scenario_id}.json").read_text())["root_cause_type"]
    state = await run_investigation(create_initial_state(load_scenario_incident(scenario_id), settings.max_iterations))
    assert state.root_cause.root_cause_type == expected


def finding(agent, hypothesis, confidence):
    return AgentFinding(investigation_id="i", agent_type=agent, hypothesis=hypothesis,
                        finding="x", evidence=["e"], confidence=confidence, reasoning="r")


def test_two_mechanisms_and_a_trigger_is_multi_layer():
    found, _ = decide_root_cause([
        finding("cicd_analyzer", H.DEPLOYMENT_INDUCED_FAILURE, 0.9),
        finding("kubernetes_analyzer", H.KUBERNETES_OOM, 0.95),
        finding("observability_analyzer", H.TRAFFIC_INCIDENT, 0.85),
    ])
    assert found == H.MULTI_LAYER_FAILURE


def test_a_mechanism_beats_a_symptom_and_a_trigger():
    found, _ = decide_root_cause([
        finding("cicd_analyzer", H.DEPLOYMENT_INDUCED_FAILURE, 0.9),
        finding("kubernetes_analyzer", H.APPLICATION_ERROR, 0.95),
        finding("observability_analyzer", H.DEPENDENCY_ISSUE, 0.8),
    ])
    assert found == H.DEPENDENCY_ISSUE


def test_all_unknown_means_nothing_wrong():
    findings = [finding("cicd_analyzer", H.UNKNOWN, 0.3), finding("kubernetes_analyzer", H.UNKNOWN, 0.3)]
    assert decide_root_cause(findings)[0] == H.UNKNOWN
    assert found_nothing(findings)
    assert not found_nothing(findings[:1])        # one specialist is not enough to call it healthy


def test_negated_words_do_not_trigger_the_pre_filter():
    cleaned = _without_negated("Healthy service. No recent config changes or deployments. Pods not ready.")
    assert "deployment" not in cleaned and "config" not in cleaned
    assert "healthy" in cleaned


# ---- dynamic agent spawner -------------------------------------------------

async def test_spawner_creates_a_cache_specialist_and_it_decides_the_root_cause():
    from backend.flow import build_trace, read_events

    state = await run_investigation(create_initial_state(load_scenario_incident("incident-008"), settings.max_iterations))
    trace = build_trace(read_events(state.investigation_id))
    assert "cache_analyzer" in trace.spawned
    assert trace.spawned["cache_analyzer"]["layer"] == "dependency"
    assert [s.node for s in trace.steps if s.node == "spawn_agent"] == ["spawn_agent"]
    assert state.agents_invoked[0] == "cache_analyzer"        # the spawned agent runs first
    assert state.root_cause.root_cause_type == "dependency_issue"


def test_spawn_skips_agents_that_already_exist_and_forgets_after_the_run():
    from backend.runtime.spawner import find_focuses, forget, requests_from_text, spawn, spawned_for

    assert [f.key for f in find_focuses("redis maxmemory reached, evicting keys")][:1] == ["cache"]
    assert spawn("run-1", requests_from_text(["redis is evicting keys"]), existing=["cache_analyzer"]) == []
    assert [s.name for s in spawn("run-1", requests_from_text(["redis is evicting keys"]), existing=[])] == ["cache_analyzer"]
    assert spawn("run-1", requests_from_text(["redis is evicting keys"]), existing=[]) == []      # not twice
    forget("run-1")
    assert spawned_for("run-1") == {}


def test_front_matter_makes_an_md_file_a_working_rule_based_agent():
    from backend.runtime.agent_spec import spec_from_markdown

    spec, body = spec_from_markdown("x_analyzer", "---\nkeywords: [Foo]\nevidence_types: [log]\nhypothesis: dependency_issue\n---\n# X\n")
    assert spec.has_rules and spec.keywords == ["foo"] and body.startswith("# X")
    assert not spec_from_markdown("y_analyzer", "# Y\n")[0].has_rules


# ---- API used by the dashboard ----------------------------------------------

async def test_flow_and_agents_endpoints():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.routes import agents_router, investigation_router

    state = await run_investigation(create_initial_state(load_scenario_incident("shoplite-S6"), settings.max_iterations))
    app = FastAPI()
    app.include_router(investigation_router, prefix="/api")
    app.include_router(agents_router, prefix="/api")
    client = TestClient(app)

    flow = client.get(f"/api/investigations/{state.investigation_id}/flow").json()
    assert flow["root_cause_type"] == "multi_layer_failure"
    assert {n["id"] for n in flow["pipeline"]["nodes"]} >= {"route", "invoke_agent", "spawn_agent"}
    invoke = next(n for n in flow["pipeline"]["nodes"] if n["id"] == "invoke_agent")
    assert invoke["visits"] == 3 and invoke["help"]
    assert any(e["taken"] for e in flow["pipeline"]["edges"])
    assert all("events" in s for s in flow["steps"])
    assert client.get("/api/investigations/nope/flow").status_code == 404

    agents = client.get("/api/agents").json()
    assert "cicd_analyzer" in {a["name"] for a in agents["specialists"]}
    assert "cache_analyzer" in {a["name"] for a in agents["spawnable"]}
    assert client.post("/api/agents", json={"name": "cicd_analyzer", "description": "x", "keywords": ["x"]}).status_code == 409
    assert client.post("/api/agents", json={"name": "Bad Name", "description": "x", "keywords": ["x"]}).status_code == 422


# ---- LLM call recording --------------------------------------------------------

async def test_real_llm_calls_are_recorded_with_prompt_and_answer():
    from backend.flow import build_trace, read_events
    from backend.llm import set_llm_provider
    from backend.llm.base import LLMProvider, LLMResponse

    class Prose(LLMProvider):
        provider_name, model_name = "stub", "stub-1"

        async def generate(self, request):
            return LLMResponse(content="I think it is the database.", tokens_used=7, model="stub-1")

    set_llm_provider(Prose())
    state = await run_investigation(create_initial_state(load_scenario_incident("shoplite-S2"), settings.max_iterations))
    trace = build_trace(read_events(state.investigation_id))
    route = next(s for s in trace.steps if s.node == "route")
    call = next(e for e in route.events if e["event"] == "llm_call")
    assert "I think it is the database." in call["response"] and call["prompt"] and call["tokens"] == 7
    assert route.status == "warning"            # the unusable answer is still flagged, now with its evidence


async def test_rules_mode_records_no_llm_calls():
    from backend.flow import read_events

    state = await run_investigation(create_initial_state(load_scenario_incident("shoplite-S2"), settings.max_iterations))
    assert not [e for e in read_events(state.investigation_id) if e["event"] == "llm_call"]


def test_langfuse_gets_one_trace_per_investigation_and_never_breaks_a_run(monkeypatch):
    from backend.llm import observe
    from backend.llm.base import LLMRequest, LLMResponse

    sent = []

    class Generation:
        def end(self): sent.append("ended")

    class Client:
        def create_trace_id(self, seed=None): return f"trace-of-{seed}"
        def start_observation(self, **kw): sent.append(kw); return Generation()

    monkeypatch.setattr(observe, "_langfuse", lambda: Client())
    observe.record_call("inv-1", "routing", "", LLMRequest(prompt="p", system_prompt="s"), LLMResponse(content="c", model="m", tokens_used=4), 5)
    call = sent[0]
    assert call["trace_context"] == {"trace_id": "trace-of-inv-1"}            # same investigation, same trace
    assert call["as_type"] == "generation" and call["name"] == "routing" and call["output"] == "c"
    assert call["usage_details"] == {"total": 4} and sent[1] == "ended"

    class Broken:
        def create_trace_id(self, seed=None): raise RuntimeError("langfuse is down")

    monkeypatch.setattr(observe, "_langfuse", lambda: Broken())
    observe.record_call("inv-1", "routing", "", LLMRequest(prompt="p"), LLMResponse(content="c"), 5)   # must not raise


# ---- apps and history ---------------------------------------------------------

def test_apps_group_scenarios_and_shoplite_comes_first():
    from backend.services.apps import get_app, list_apps

    apps = list_apps()
    assert apps[0]["key"] == "shoplite" and apps[0]["name"] == "ShopLite"
    assert [s["scenario_id"] for s in get_app("shoplite")["scenarios"]] == SHOPLITE
    assert get_app("shoplite")["scenarios"][1]["expected_root_cause"] == "kubernetes_oom"
    assert get_app("nope") is None


def test_app_pages_show_runs_newest_first_with_match(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api import routes

    def run(i, cause, status="completed"):
        return {"investigation_id": i, "incident_id": "shoplite-S2", "status": status, "root_cause_type": cause,
                "confidence": 0.9, "agents_invoked": [], "iterations": 2, "created_at": "2026-01-01T00:00:00",
                "completed_at": None, "duration_s": 1.0}

    async def fake_runs(incident_ids=None):
        return {"shoplite-S2": [run("new", "kubernetes_oom"), run("old", "unknown"), run("failed", None, "failed")]}

    monkeypatch.setattr("backend.services.history.runs_by_incident", fake_runs)
    app = FastAPI()
    for r in (routes.apps_router, routes.router):
        app.include_router(r, prefix="/api")
    client = TestClient(app)

    page = client.get("/api/apps/shoplite").json()
    s2 = next(s for s in page["scenarios"] if s["scenario_id"] == "shoplite-S2")
    assert [(r["investigation_id"], r["matches_expected"]) for r in s2["runs"]] == [("new", True), ("old", False), ("failed", None)]
    listing = client.get("/api/apps").json()["apps"]
    assert listing[0]["key"] == "shoplite" and listing[0]["run_count"] == 3
    assert client.get("/api/apps/nope").status_code == 404
    assert len(client.get("/api/incidents/shoplite-S2/runs").json()["runs"]) == 3


# ---- persistence and interrupted runs ------------------------------------------

async def test_insert_new_batches_and_skips_what_is_already_stored():
    from backend.orchestrator.state import MongoStateManager

    calls = {"find": 0, "insert_many": []}

    class Item:
        def __init__(self, i): self.item_id = i

    class FakeQuery:
        def __init__(self, found): self.found = found
        async def to_list(self): return self.found

    class FakeDoc:
        item_id = None
        @classmethod
        def find(cls, query):
            calls["find"] += 1
            return FakeQuery([Item("a")] if "a" in query["item_id"]["$in"] else [])
        @classmethod
        async def insert_many(cls, docs): calls["insert_many"].append([d.item_id for d in docs])

    manager = MongoStateManager()
    await manager._insert_new(FakeDoc, "item_id", [Item("a"), Item("b"), Item("c")], lambda i: i, "inv")
    assert calls["find"] == 1 and calls["insert_many"] == [["b", "c"]]       # "a" was already stored
    await manager._insert_new(FakeDoc, "item_id", [Item("a"), Item("b"), Item("c")], lambda i: i, "inv")
    assert calls["find"] == 1                                                 # nothing new: no query at all
    await manager._insert_new(FakeDoc, "item_id", [Item("d")], lambda i: i, "inv")
    assert calls["find"] == 2 and calls["insert_many"][-1] == ["d"]


def test_interrupted_is_a_known_status_and_counts_as_finished():
    from backend.models import InvestigationStatus
    from backend.orchestrator.state import _FINISHED

    assert InvestigationStatus.INTERRUPTED in _FINISHED
    assert InvestigationStatus.RUNNING not in _FINISHED


# ---- the confidence formula ----------------------------------------------------

def _ev(i, c):
    from backend.models import Evidence, EvidenceType
    return Evidence(evidence_id=i, investigation_id="i", agent_type="a", evidence_type=EvidenceType.LOG,
                    description="d", raw_data={}, confidence=c, source="t")


def _f(agent, h, conf, cites):
    return AgentFinding(investigation_id="i", agent_type=agent, hypothesis=h, finding="x", evidence=cites, confidence=conf, reasoning="r")


def test_finding_score_formula_with_exact_numbers():
    from backend.orchestrator.scoring import score_finding

    evidence = [_ev("e1", 0.9), _ev("e2", 0.8), _ev("e3", 0.7)]
    s = score_finding(_f("k", H.KUBERNETES_OOM, 0.90, ["e1", "e2", "e3"]), evidence)
    # 1.0 x (0.5 x 0.90 + 0.3 x 0.80 + 0.2 x 1.0) = 0.45 + 0.24 + 0.20
    assert (s.strength, s.coverage, s.grounding, s.score) == (0.8, 1.0, 1.0, 0.89)
    # one real item, one invented: grounding 0.5, strength 0.9, coverage 1/3
    half = score_finding(_f("k", H.KUBERNETES_OOM, 0.90, ["e1", "ghost"]), evidence)
    assert half.grounding == 0.5 and half.score == round(0.5 * (0.45 + 0.27 + 0.2 / 3), 2)
    # invented evidence scores zero however sure the agent is
    assert score_finding(_f("k", H.KUBERNETES_OOM, 0.99, ["ghost"]), evidence).score == 0.0
    assert score_finding(_f("k", H.KUBERNETES_OOM, 0.99, []), evidence).score == 0.0


def test_investigation_confidence_terms():
    from backend.models import CriticReview
    from backend.orchestrator.scoring import score_investigation

    evidence = [_ev(f"e{i}", 0.9) for i in range(6)]
    oom = _f("kubernetes_analyzer", H.KUBERNETES_OOM, 0.9, ["e0", "e1", "e2"])      # score 0.5*.9+.3*.9+.2 = 0.92
    agree = _f("observability_analyzer", H.KUBERNETES_OOM, 0.8, ["e3", "e4", "e5"])  # 0.87
    rival = _f("config_analyzer", H.CONFIGURATION_ERROR, 0.8, ["e3", "e4", "e5"])    # strong, different mechanism

    alone = score_investigation([oom], evidence)
    assert alone.hypothesis == "kubernetes_oom" and alone.base == 0.92 and alone.overall == 0.92

    both = score_investigation([oom, agree], evidence)
    assert both.corroboration == 0.05 and both.overall == 0.97                       # a second layer helps

    disputed = score_investigation([oom, rival], evidence)
    assert disputed.contradiction == 0.15 and disputed.overall == 0.77              # a rival mechanism hurts

    gaps = score_investigation([oom], evidence, evidence_gaps=["a", "b", "critic: ignore me"])
    assert gaps.open_gaps == 0.10 and gaps.overall == 0.82                           # critic notes are not gaps

    challenged = CriticReview(investigation_id="i", round=1, verdict="challenged", confidence=0.6)
    assert score_investigation([oom], evidence, critic=challenged).overall == round(0.92 * 0.8, 2)

    assert score_investigation([_f("k", H.KUBERNETES_OOM, 0.99, ["ghost"])], evidence).overall == 0.0


def test_multi_layer_failure_is_not_punished_for_its_own_parts():
    from backend.orchestrator.scoring import score_investigation

    evidence = [_ev(f"e{i}", 0.9) for i in range(9)]
    b = score_investigation([
        _f("cicd_analyzer", H.DEPLOYMENT_INDUCED_FAILURE, 0.9, ["e0", "e1", "e2"]),
        _f("kubernetes_analyzer", H.KUBERNETES_OOM, 0.95, ["e3", "e4", "e5"]),
        _f("observability_analyzer", H.TRAFFIC_INCIDENT, 0.85, ["e6", "e7", "e8"]),
    ], evidence)
    assert b.hypothesis == "multi_layer_failure" and b.contradiction == 0.0 and b.corroboration == 0.10


def test_nothing_found_stays_low_even_with_lots_of_evidence():
    from backend.orchestrator.scoring import score_investigation

    evidence = [_ev(f"e{i}", 0.9) for i in range(6)]
    b = score_investigation([_f("a", H.UNKNOWN, 0.3, ["e0", "e1", "e2"]), _f("b", H.UNKNOWN, 0.3, ["e3", "e4", "e5"])], evidence)
    assert b.hypothesis == "unknown" and b.overall == 0.3 and b.corroboration == 0.0


# ---- evidence selection for prompts ---------------------------------------------

def test_evidence_selection_keeps_every_layer_and_says_what_was_left_out():
    from backend.models import Evidence, EvidenceType
    from backend.runtime.evidence_view import format_evidence, select_evidence

    def ev(i, agent, kind, conf):
        return Evidence(evidence_id=i, investigation_id="i", agent_type=agent, evidence_type=kind,
                        description=f"item {i}", raw_data={}, confidence=conf, source="t")

    # 6 CI/CD items loaded first, then 60 log lines: "the last 40" would drop all of CI/CD.
    items = [ev(f"c{i}", "cicd_analyzer", EvidenceType.CONFIG_CHANGE, 0.8) for i in range(6)]
    items += [ev(f"l{i}", "observability_analyzer", EvidenceType.LOG, 0.5) for i in range(60)]
    items.append(ev("lat", "observability_analyzer", EvidenceType.LATENCY, 0.9))

    shown = select_evidence(items, 20)
    assert len(shown) == 20 and any(e.agent_type == "cicd_analyzer" for e in shown)
    assert any(e.evidence_type == EvidenceType.LATENCY for e in shown)            # the strongest of each type survives
    assert [e.evidence_id for e in shown] == [e.evidence_id for e in items if e in shown]   # original order kept

    focused = select_evidence(items, 20, focus_agent="cicd_analyzer")
    assert sum(e.agent_type == "cicd_analyzer" for e in focused) == 6             # own layer first (it has only 6)
    text = format_evidence(items, limit=20)
    assert "more items not shown" in text and "log" in text
    assert "not shown" not in format_evidence(items[:5], limit=20)


def test_a_release_alone_is_not_a_failure():
    findings = [finding("cicd_analyzer", H.DEPLOYMENT_INDUCED_FAILURE, 0.6),
                finding("kubernetes_analyzer", H.UNKNOWN, 0.3), finding("observability_analyzer", H.UNKNOWN, 0.3)]
    assert decide_root_cause(findings)[0] == H.UNKNOWN
    assert found_nothing(findings)
    # ... but a strong deployment finding, or a weak one with nothing to contradict it, still counts
    assert decide_root_cause([finding("cicd_analyzer", H.DEPLOYMENT_INDUCED_FAILURE, 0.9)])[0] == H.DEPLOYMENT_INDUCED_FAILURE
    assert decide_root_cause([finding("cicd_analyzer", H.DEPLOYMENT_INDUCED_FAILURE, 0.6)])[0] == H.DEPLOYMENT_INDUCED_FAILURE


# ---- live lab and evaluation ----------------------------------------------------

def test_live_incident_text_never_names_the_injected_fault():
    from backend.live.shoplite import EXPECTED, _Probe, _Supervisor, describe

    for fault in EXPECTED:
        sup = _Supervisor(fault, 128, 0)
        sup.restarts, sup.ever_ready = (3, False) if fault == "bad_config" else (1 if fault == "oom" else 0, True)
        probes = [_Probe("/health", 503 if fault == "db_down" else 200, 20.0, 0.0)] * 5
        obs = {"error_rate": {"rate": 100.0 if fault != "none" else 0.0}, "latency": {"p99": 20}}
        title, description = describe(probes, sup, obs)
        text = f"{title} {description}".lower()
        for word in (fault, fault.replace("_", " "), "oom", "leak", "injected", "fault"):
            if word not in ("none", "latency"):          # "latency" is also an ordinary symptom word
                assert word not in text, f"{fault}: incident text leaks '{word}'"


@pytest.mark.skipif(not (__import__("backend.live.shoplite", fromlist=["SHOPLITE_DIR"]).SHOPLITE_DIR / "app" / "main.py").exists(),
                    reason="ShopLite checkout not found (set SHOPLITE_DIR)")
async def test_live_lab_runs_a_real_broken_shoplite_and_the_investigator_diagnoses_it():
    from backend.live.shoplite import run_lab

    lab = await run_lab("bad_config")              # the real process refuses to start: a real restart loop
    assert lab.summary["restarts"] >= 1 and lab.summary["last_exit"] not in (None, 0)
    assert any("REQUIRED_SECRET" in e.description for e in lab.evidence)
    assert all(e.source == "live_shoplite" for e in lab.evidence)

    state = create_initial_state(lab.incident, settings.max_iterations)
    state.evidence = lab.evidence
    final = await run_investigation(state)
    assert final.root_cause.root_cause_type == "configuration_error"
    assert not [e for e in final.evidence if str(e.source) != "live_shoplite"]      # no fixture evidence mixed in


def test_evaluation_statistics():
    import importlib.util
    spec = importlib.util.spec_from_file_location("evaluate", Path(__file__).resolve().parent.parent / "scripts" / "evaluate.py")
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)

    def row(expected, got, conf):
        return {"expected": expected, "got": got, "correct": expected == got, "confidence": conf, "seconds": 1.0,
                "llm_calls": 2, "llm_tokens": 10, "fallbacks": 0}

    s = ev.summarize([row("kubernetes_oom", "kubernetes_oom", 0.9), row("kubernetes_oom", "unknown", 0.8),
                      row("dependency_issue", "dependency_issue", 0.6), row("unknown", "unknown", 0.3), row("unknown", "kubernetes_oom", 0.8)])
    assert s["accuracy"] == 0.6 and s["false_alarms"] == "1/2"
    assert s["brier"] == round(((0.9 - 1) ** 2 + (0.8 - 0) ** 2 + (0.6 - 1) ** 2) / 3, 2)      # healthy rows are not in Brier
    assert [b["n"] for b in s["calibration"]] == [0, 1, 1, 1]
