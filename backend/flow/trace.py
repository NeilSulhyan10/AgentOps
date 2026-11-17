"""
Flow trace: the story of one investigation, built from its flow-log events.

The flow log (see ``backend/flow/log.py``) is a flat list of events.  This
module folds the events of one investigation into an ordered list of ``Step``
objects, each tagged ``ok``, ``warning`` or ``error``.  Everything a developer
sees (terminal summary, diagrams, HTML report, API) is rendered from a
``FlowTrace`` - nothing else decides what counts as a problem.

What makes a step a problem
---------------------------
==================  ========  ===================================================
Step                Status    When
==================  ========  ===================================================
route               warning   the LLM's answer was unusable or named an unknown
                              agent, so the rule-based router chose instead
route               warning   routing stopped because max_iterations was reached
invoke_agent        warning   the LLM's answer was unusable (rules took over)
invoke_agent        warning   the finding cites no evidence that exists, so it
                              does not count towards confidence
critique            warning   the critic challenged and nothing was left to try
                              (a challenge that sends the run back is normal: ok)
generate_rca        warning   the LLM's answer was unusable, or the investigation
                              ended without reaching the confidence threshold
any node            error     the node raised an exception (investigation failed)
==================  ========  ===================================================
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

OK, WARNING, ERROR = "ok", "warning", "error"

# The flow-log "task" of an LLM call -> the graph node that made the call.
_TASK_NODE = {
    "routing": "route",
    "analysis": "invoke_agent",
    "critic": "critique",
    "rca": "generate_rca",
    "remediation": "generate_rca",
}


@dataclass
class Step:
    """One thing that happened, in order, at one node of the graph."""

    node: str                       # graph node name, e.g. "route"
    title: str                      # short label, e.g. "Route #1 -> cicd_analyzer"
    status: str = OK                # ok | warning | error
    notes: List[str] = field(default_factory=list)   # plain-language details
    duration_ms: Optional[int] = None
    events: List[dict] = field(default_factory=list)   # the raw flow-log events behind this step

    def problem(self, status: str, note: str) -> None:
        """Record a problem; an error is never downgraded to a warning."""
        if self.status != ERROR:
            self.status = status
        self.notes.append(note)


@dataclass
class FlowTrace:
    investigation_id: str
    incident_id: str = ""
    title: str = ""
    service: str = ""
    engine: str = ""                # "llm:<provider>" or "rules"
    fault: str = ""                 # injected fault, if any (showcase runs)
    steps: List[Step] = field(default_factory=list)
    final_status: str = "running"
    root_cause_type: str = ""
    confidence: float = 0.0
    # agent name -> {"hypothesis": str, "confidence": float, "grounded": bool}
    findings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # the latest confidence breakdown (see backend/orchestrator/scoring.py); empty until a step has scored one
    confidence_breakdown: Dict[str, Any] = field(default_factory=dict)
    # agent name -> spec dict, for specialists spawned during this investigation
    spawned: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @property
    def problems(self) -> List[Step]:
        return [s for s in self.steps if s.status != OK]

    @property
    def worst_status(self) -> str:
        statuses = {s.status for s in self.steps}
        return ERROR if ERROR in statuses else WARNING if WARNING in statuses else OK


def group_by_investigation(events: List[dict]) -> Dict[str, List[dict]]:
    """Split a flow log into one event list per investigation, oldest first."""
    runs: Dict[str, List[dict]] = {}
    for event in events:
        if event.get("investigation_id"):
            runs.setdefault(event["investigation_id"], []).append(event)
    for run in runs.values():
        run.sort(key=lambda e: e.get("ts", ""))
    return runs


def build_trace(events: List[dict]) -> FlowTrace:
    """Fold the events of ONE investigation into a FlowTrace."""
    if not events:
        raise ValueError("no flow events for this investigation")
    builder = _TraceBuilder(events[0]["investigation_id"])
    for event in events:
        handler = builder.handlers.get(event["event"])
        if handler:
            handler(event)
    return builder.trace


class _TraceBuilder:
    """Holds the small amount of state needed while reading events in order."""

    def __init__(self, investigation_id: str):
        self.trace = FlowTrace(investigation_id=investigation_id)
        # An "LLM answer unusable" event is logged *before* the step that used
        # the fallback, so it waits here until that step is created.
        self._pending_fallbacks: Dict[str, List[tuple]] = {}
        self._pending_calls: Dict[str, List[dict]] = {}
        self.handlers: Dict[str, Callable[[dict], None]] = {
            "investigation_started": self._started,
            "pre_filter": self._pre_filter,
            "load_evidence": self._load_evidence,
            "agent_spawned": self._spawned,
            "llm_parse_fallback": self._llm_fallback,
            "llm_call": self._llm_call,
            "route": self._route,
            "route_stopped": self._route_stopped,
            "agent_finding": self._agent_finding,
            "evaluate": self._evaluate,
            "critic": self._critic,
            "rca": self._rca,
            "node_failed": self._node_failed,
            "investigation_finished": self._finished,
        }

    # -- helpers ------------------------------------------------------------

    def _add(self, node: str, title: str, event: dict) -> Step:
        step = Step(node=node, title=title, duration_ms=event.get("duration_ms"), events=[event])
        for note, fallback_event in self._pending_fallbacks.pop(node, []):
            step.problem(WARNING, note)
            step.events.insert(0, fallback_event)
        step.events[:0] = self._pending_calls.pop(node, [])
        self.trace.steps.append(step)
        return step

    # -- one handler per event type -------------------------------------------

    def _started(self, e: dict) -> None:
        t = self.trace
        t.incident_id = e.get("incident_id", "")
        t.title = e.get("title", "")
        t.service = e.get("service_name", "")
        t.engine = e.get("engine", "")
        t.fault = e.get("fault", "")
        step = self._add("normalize", "Start investigation", e)
        step.notes.append(f"Incident {t.incident_id}: {t.title}")
        step.notes.append(f"Decisions made by: {t.engine or 'unknown'}")
        if t.fault:
            step.notes.append(f"Injected fault for this demo run: {t.fault}")

    def _pre_filter(self, e: dict) -> None:
        self.trace.incident_id = self.trace.incident_id or e.get("incident_id", "")
        self.trace.title = self.trace.title or e.get("title", "")
        step = self._add("pre_filter", "Keyword pre-filter", e)
        step.notes.append(f"First guess: {e.get('hypothesis')}")
        if e.get("evidence_gaps"):
            step.notes.append("Wants to know about: " + ", ".join(e["evidence_gaps"]))

    def _load_evidence(self, e: dict) -> None:
        total = e.get("total_evidence", 0)
        step = self._add("load_evidence", f"Load evidence ({total} items)", e)
        if e.get("sources"):
            step.notes.append("Sources: " + ", ".join(e["sources"]))
        if total == 0:
            step.problem(WARNING, "No evidence was found for this incident; every finding will be ungrounded.")

    def _spawned(self, e: dict) -> None:
        name = e.get("agent", "?")
        self.trace.spawned[name] = {k: e.get(k) for k in ("layer", "hypothesis", "description", "keywords", "reason")}
        step = self._add("spawn_agent", f"Spawned {name}", e)
        step.notes.append(f"No available specialist covers this, so {name} was created: {e.get('description')}")
        step.notes.append(f"Because: {_short(e.get('reason'), 200)}")

    def _llm_call(self, e: dict) -> None:
        # Like a fallback notice, the call is logged before the step that used it; it is evidence, not a problem.
        node = _TASK_NODE.get(e.get("task", ""), "invoke_agent")
        self._pending_calls.setdefault(node, []).append(e)

    def _llm_fallback(self, e: dict) -> None:
        node = _TASK_NODE.get(e.get("task", ""), "invoke_agent")
        who = f" ({e['agent']})" if e.get("agent") else ""
        note = f"LLM answer for {e.get('task')}{who} was unusable; rules took over. {_short(e.get('error'))}"
        self._pending_fallbacks.setdefault(node, []).append((note, e))

    def _route(self, e: dict) -> None:
        step = self._add("route", f"Route #{e.get('iteration')} -> {e.get('selected_agent')}", e)
        step.notes.append(_short(e.get("reasoning"), 220))
        llm_choice = e.get("llm_choice")
        if e.get("used_deterministic_fallback") and llm_choice:
            step.problem(WARNING, f"LLM chose '{llm_choice}', which is not an available agent; the rule-based router chose instead.")

    def _route_stopped(self, e: dict) -> None:
        step = self._add("route", "Routing stopped", e)
        step.problem(WARNING, f"Stopped before reaching enough confidence: {e.get('reason')} (iteration {e.get('iteration')}).")

    def _agent_finding(self, e: dict) -> None:
        agent, hypothesis = e.get("agent", "?"), e.get("hypothesis", "unknown")
        grounded, cited = e.get("grounded_evidence", 0), e.get("cited_evidence", 0)
        step = self._add("invoke_agent", f"{agent}: {hypothesis} ({e.get('confidence', 0):.2f})", e)
        step.notes.append(_short(e.get("finding"), 300))
        step.notes.append(f"Evidence cited: {cited}, of which real: {grounded}")
        if cited and not grounded:
            step.problem(WARNING, "The finding cites evidence ids that do not exist, so it is ignored when computing confidence.")
        self.trace.findings[agent] = {
            "hypothesis": hypothesis,
            "confidence": e.get("confidence", 0.0),
            "grounded": grounded > 0,
        }

    def _evaluate(self, e: dict) -> None:
        self.trace.confidence_breakdown = e.get("breakdown") or self.trace.confidence_breakdown
        overall, threshold = e.get("overall_confidence", 0.0), e.get("threshold", 0.0)
        verdict = "enough" if e.get("is_sufficient") else "not enough yet"
        step = self._add("evaluate", f"Confidence {overall:.2f} / {threshold:.2f} ({verdict})", e)
        per_agent = e.get("agent_confidences") or {}
        if per_agent:
            step.notes.append("Per agent: " + ", ".join(f"{a} {c:.2f}" for a, c in per_agent.items()))

    def _critic(self, e: dict) -> None:
        self.trace.confidence_breakdown = e.get("breakdown") or self.trace.confidence_breakdown
        step = self._add("critique", f"Critic #{e.get('round')}: {e.get('verdict')} ({e.get('confidence', 0):.2f})", e)
        if e.get("verdict") != "challenged":
            return
        concerns = e.get("concerns") or ["The critic challenged the conclusion."]
        if e.get("looping_back"):
            # The critic doing its job: it asked for another specialist.  Not a problem.
            step.notes.extend(concerns)
            step.notes.append(f"Sent back to the router; suggested agent: {e.get('suggested_agent')}")
        else:
            # Nothing left to try: the report goes out with the doubt still attached.
            for concern in concerns:
                step.problem(WARNING, concern)
            step.notes.append("Could not loop back (no rounds, iterations or unused agents left); the root cause is reported with this concern unresolved.")

    def _rca(self, e: dict) -> None:
        t = self.trace
        t.root_cause_type = e.get("root_cause_type") or "unknown"
        t.confidence = e.get("overall_confidence", 0.0)
        step = self._add("generate_rca", f"Root cause: {t.root_cause_type} ({t.confidence:.2f})", e)
        step.notes.append("Agents used: " + (" -> ".join(e.get("agents_invoked") or []) or "none"))
        if e.get("status") == "max_iterations_reached":
            step.problem(WARNING, "The investigation ran out of iterations before reaching the confidence threshold.")

    def _node_failed(self, e: dict) -> None:
        who = f" ({e['agent']})" if e.get("agent") else ""
        step = self._add(e.get("node", "?"), f"{e.get('node')}{who} FAILED", e)
        step.problem(ERROR, _short(e.get("error"), 400))

    def _finished(self, e: dict) -> None:
        self.trace.final_status = e.get("status", "unknown")
        if self.trace.final_status == "failed":
            return  # the failing node already has its own red step
        self._add("persist", f"Finished: {self.trace.final_status}", e)


def _short(text: Any, limit: int = 160) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
