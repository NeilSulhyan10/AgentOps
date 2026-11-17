"""
Mermaid diagrams for a FlowTrace.

Two diagrams answer the two questions a developer asks after an investigation:

* ``app_map``      - WHERE IN MY APP is the fault?  (layers of the investigated app)
* ``pipeline_map`` - WHERE IN AGENTOPS did the investigation go wrong, if it did?
                     (the LangGraph nodes, coloured by what happened at each)

Both return Mermaid text, which renders natively on GitHub, in VS Code and in
the HTML report (``backend/flow/report.py``).

Colours mean the same thing in both diagrams:
    green = fine, amber = worth a look, red = the fault, grey dashed = not visited.
"""

from typing import Dict, List

from backend.flow.layers import AFFECTED, CLEAR, LAYER_EDGES, LAYERS, NOT_CHECKED, ROOT, layer_statuses
from backend.flow.trace import ERROR, OK, WARNING, FlowTrace

# The investigation graph.  This must mirror build_investigation_graph() in
# backend/orchestrator/graph.py; tests/test_flow.py fails if the two drift apart.
PIPELINE_NODES: Dict[str, str] = {
    "normalize": "mark investigation as running",
    "pre_filter": "keyword-based first guess",
    "load_evidence": "collect CI/CD, Kubernetes, observability evidence",
    "spawn_agent": "create a specialist if none covers a problem",
    "route": "choose the next specialist",
    "invoke_agent": "run that specialist",
    "evaluate": "is confidence high enough?",
    "critique": "critic reviews the conclusion",
    "generate_rca": "write root cause + remediation",
    "persist": "finish",
}

PIPELINE_EDGES: List[tuple] = [
    ("normalize", "pre_filter"),
    ("pre_filter", "load_evidence"),
    ("load_evidence", "spawn_agent"),
    ("spawn_agent", "route"),
    ("route", "invoke_agent"),
    ("route", "generate_rca"),       # max_iterations reached
    ("invoke_agent", "evaluate"),
    ("evaluate", "route"),           # not confident enough: ask another specialist
    ("evaluate", "critique"),
    ("critique", "spawn_agent"),     # critic challenged: ask another specialist (spawning one if needed)
    ("critique", "generate_rca"),
    ("generate_rca", "persist"),
]

SKIPPED = "skipped"

_CLASS_DEFS = [
    "classDef ok fill:#d1f2d9,stroke:#1a7f37,color:#0b2e13",
    "classDef warning fill:#fff1c2,stroke:#9a6700,color:#3b2a00",
    "classDef error fill:#ffd7d5,stroke:#cf222e,color:#5c0a0f,stroke-width:3px",
    "classDef skipped fill:#f3f3f3,stroke:#999999,color:#666666,stroke-dasharray:4 3",
]

_LAYER_CLASS = {ROOT: ERROR, AFFECTED: WARNING, CLEAR: OK, NOT_CHECKED: SKIPPED}


def app_map(trace: FlowTrace) -> str:
    """Layers of the investigated application; the root-cause layer is red."""
    statuses = layer_statuses(trace)
    lines = ["flowchart LR"]
    for layer in LAYERS:
        st = statuses[layer.key]
        label = _label(layer.name, layer.watches, st.detail)
        lines.append(f'    {layer.key}["{label}"]:::{_LAYER_CLASS[st.status]}')
    for source, target in LAYER_EDGES:
        lines.append(f"    {source} --> {target}")
    return "\n".join(lines + [f"    {d}" for d in _CLASS_DEFS])


def walked_edges(trace: FlowTrace) -> set:
    """Edges of the pipeline the investigation actually travelled."""
    edges = set(PIPELINE_EDGES)
    nodes = [s.node for s in trace.steps]
    walked = set()
    for a, b in zip(nodes, nodes[1:]):
        if (a, b) in edges:
            walked.add((a, b))
        elif (a, "spawn_agent") in edges and ("spawn_agent", b) in edges:
            # spawn_agent ran but had nothing to spawn, so it left no step of its own
            walked |= {(a, "spawn_agent"), ("spawn_agent", b)}
    return walked


def node_states(trace: FlowTrace) -> Dict[str, dict]:
    """For each pipeline node: status (ok/warning/error/skipped), number of visits and a one-line summary."""
    walked = walked_edges(trace)
    states: Dict[str, dict] = {}
    for node in PIPELINE_NODES:
        steps = [s for s in trace.steps if s.node == node]
        status = SKIPPED
        for step in steps:
            status = step.status if status == SKIPPED else _worse(status, step.status)
        if not steps and any(node in edge for edge in walked):
            states[node] = {"status": OK, "visits": 0, "summary": "ran, nothing to do"}
        else:
            states[node] = {"status": status, "visits": len(steps), "summary": _node_extra(trace, node, len(steps))}
    return states


def pipeline_map(trace: FlowTrace) -> str:
    """The investigation graph; each node is coloured by the worst thing that happened there."""
    states = node_states(trace)
    lines = ["flowchart TD"]
    for node, purpose in PIPELINE_NODES.items():
        lines.append(f'    {node}["{_label(node, purpose, states[node]["summary"])}"]:::{states[node]["status"]}')

    walked = walked_edges(trace)
    walked_indexes = []
    for index, (source, target) in enumerate(PIPELINE_EDGES):
        lines.append(f"    {source} --> {target}")
        if (source, target) in walked:
            walked_indexes.append(str(index))
    if walked_indexes:  # draw the path that was actually taken with a thick line
        lines.append(f"    linkStyle {','.join(walked_indexes)} stroke-width:3px")
    return "\n".join(lines + [f"    {d}" for d in _CLASS_DEFS])


def _node_extra(trace: FlowTrace, node: str, visits: int) -> str:
    """Third line of a pipeline node: what actually happened there."""
    if not visits:
        return "not reached"
    steps = [s for s in trace.steps if s.node == node]
    failed = [s for s in steps if s.status == ERROR]
    if failed:
        return failed[0].title
    if node == "invoke_agent":
        return "ran: " + ", ".join(trace.findings) if trace.findings else "ran"
    if node == "spawn_agent":
        return "spawned: " + ", ".join(trace.spawned)
    if node in ("route", "evaluate", "critique") and visits > 1:
        return f"visited {visits} times"
    return steps[-1].title


def _worse(a: str, b: str) -> str:
    order = [OK, WARNING, ERROR]
    return a if order.index(a) >= order.index(b) else b


def _label(*parts: str) -> str:
    """Join label lines for a Mermaid node, removing characters Mermaid would misread."""
    cleaned = []
    for part in parts:
        text = " ".join(str(part).split())
        # Inside a quoted label only these three are special: quote, tag start, entity start.
        for bad, good in (('"', "'"), ("<", "("), ("#", "")):
            text = text.replace(bad, good)
        cleaned.append(text[:70])
    return "<br/>".join(cleaned)
