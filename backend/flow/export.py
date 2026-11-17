"""FlowTrace -> plain dict (JSON for the dashboard API)."""

from typing import Any, Dict

from backend.flow.diagram import PIPELINE_EDGES, PIPELINE_NODES, node_states, walked_edges
from backend.flow.layers import LAYER_EDGES, layer_statuses
from backend.flow.report import headline
from backend.flow.trace import FlowTrace

# One sentence per node: what it does, for the "what is this step?" panel.
NODE_HELP: Dict[str, str] = {
    "normalize": "Marks the investigation as running.",
    "pre_filter": "Reads the incident text for keywords and makes a first guess plus a list of things to check (evidence gaps). Words after 'no' or 'not' are ignored.",
    "load_evidence": "Collects CI/CD, Kubernetes and observability evidence for the incident.",
    "spawn_agent": "Creates a new specialist when the incident or the critic points at a problem none of the existing specialists owns (cache, queue, DNS, disk, certificates, rate limits).",
    "route": "Chooses which specialist looks next: the LLM when one is configured, otherwise rules based on the gaps, the first guess and the critic's advice.",
    "invoke_agent": "Runs the chosen specialist on the evidence. It returns a hypothesis, a confidence and the evidence it cites. Findings that cite no real evidence are ignored.",
    "evaluate": "Takes the highest confidence among grounded findings and compares it to the threshold. All specialists reporting 'nothing wrong' also ends the loop.",
    "critique": "The critic reviews all findings as one causal chain. It challenges when the conclusion rests on one layer, contradicts itself, or something flagged was never checked.",
    "generate_rca": "Decides the root-cause type (mechanism over trigger over symptom; several mechanisms plus a trigger is a multi-layer failure) and writes the report and remediation.",
    "persist": "Finishes the run.",
}


def trace_to_dict(trace: FlowTrace) -> Dict[str, Any]:
    states = node_states(trace)
    walked = walked_edges(trace)
    layers = layer_statuses(trace)
    return {
        "investigation_id": trace.investigation_id,
        "incident_id": trace.incident_id,
        "title": trace.title,
        "service": trace.service,
        "engine": trace.engine,
        "fault": trace.fault,
        "final_status": trace.final_status,
        "root_cause_type": trace.root_cause_type,
        "confidence": trace.confidence,
        "headline": headline(trace),
        "worst_status": trace.worst_status,
        "steps": [
            {"index": i + 1, "node": s.node, "title": s.title, "status": s.status, "notes": s.notes,
             "duration_ms": s.duration_ms, "events": s.events}
            for i, s in enumerate(trace.steps)
        ],
        "pipeline": {
            "nodes": [{"id": n, "purpose": p, "help": NODE_HELP.get(n, ""), **states[n]} for n, p in PIPELINE_NODES.items()],
            "edges": [{"source": a, "target": b, "taken": (a, b) in walked} for a, b in PIPELINE_EDGES],
        },
        "layers": [
            {"key": l.layer.key, "name": l.layer.name, "watches": l.layer.watches, "agent": l.layer.agent,
             "status": l.status, "detail": l.detail}
            for l in layers.values()
        ],
        "layer_edges": [{"source": a, "target": b} for a, b in LAYER_EDGES],
        "findings": trace.findings,
        "confidence_breakdown": trace.confidence_breakdown,
        "spawned": trace.spawned,
    }
