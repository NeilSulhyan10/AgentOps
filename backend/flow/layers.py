"""
App map: which layer of the *investigated application* is at fault.

An application under investigation is modelled as six layers.  Each layer is
owned by one specialist agent and is the home of one root-cause type:

    layer         specialist               root-cause type
    ------------  -----------------------  --------------------------
    cicd          cicd_analyzer            deployment_induced_failure
    config        config_analyzer          configuration_error
    kubernetes    kubernetes_analyzer      kubernetes_oom
    service       observability_analyzer   application_error
    traffic       traffic_analyzer         traffic_incident
    dependency    dependency_analyzer      dependency_issue

``layer_statuses`` reads a FlowTrace and labels every layer:

    root         the root cause was placed here
    affected     its specialist found real evidence of trouble here (a symptom
                 or a contributing factor), but it is not the root cause
    clear        its specialist looked and found nothing
    not_checked  its specialist was never called
"""

from dataclasses import dataclass
from typing import Dict, List

from backend.flow.trace import FlowTrace

ROOT, AFFECTED, CLEAR, NOT_CHECKED = "root", "affected", "clear", "not_checked"


@dataclass(frozen=True)
class Layer:
    key: str
    name: str
    watches: str        # what lives in this layer
    agent: str          # specialist that inspects it
    root_cause_type: str


LAYERS: List[Layer] = [
    Layer("cicd", "CI/CD pipeline", "build, tests, deploy", "cicd_analyzer", "deployment_induced_failure"),
    Layer("config", "Configuration", "env vars, secrets, probes", "config_analyzer", "configuration_error"),
    Layer("kubernetes", "Kubernetes", "pods, memory limits, restarts", "kubernetes_analyzer", "kubernetes_oom"),
    Layer("service", "Service", "latency, error rate, logs", "observability_analyzer", "application_error"),
    Layer("traffic", "Traffic", "user load", "traffic_analyzer", "traffic_incident"),
    Layer("dependency", "Dependencies", "database, downstream services", "dependency_analyzer", "dependency_issue"),
]

# How a change travels through the layers until users notice it.
LAYER_EDGES = [
    ("cicd", "kubernetes"),
    ("config", "kubernetes"),
    ("kubernetes", "service"),
    ("traffic", "service"),
    ("service", "dependency"),
]


@dataclass
class LayerStatus:
    layer: Layer
    status: str
    detail: str


def layer_statuses(trace: FlowTrace) -> Dict[str, LayerStatus]:
    result: Dict[str, LayerStatus] = {}
    for layer in LAYERS:
        # The layer's own specialist, or one spawned for this layer (e.g. cache_analyzer -> dependency).
        owners = [layer.agent] + [n for n, s in trace.spawned.items() if s.get("layer") == layer.key]
        finding = next((trace.findings[n] for n in owners if n in trace.findings), None)
        if finding is None:
            status, detail = NOT_CHECKED, "not checked"
        elif finding["grounded"] and finding["hypothesis"] != "unknown":
            status = AFFECTED
            detail = f"{finding['hypothesis']} ({finding['confidence']:.2f})"
        else:
            status, detail = CLEAR, "checked, nothing found"

        is_root = trace.root_cause_type == layer.root_cause_type
        # A multi-layer failure has no single home: every layer with real findings is part of the cause.
        if trace.root_cause_type == "multi_layer_failure" and status == AFFECTED:
            is_root = True
        if is_root:
            status = ROOT
            detail = f"ROOT CAUSE: {trace.root_cause_type}"
            if finding and finding["grounded"]:
                detail += f" ({finding['confidence']:.2f})"

        result[layer.key] = LayerStatus(layer, status, detail)
    return result
