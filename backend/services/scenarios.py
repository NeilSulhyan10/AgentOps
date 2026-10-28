"""
Scenario catalogue: every data/incidents/<id>.json is a replayable incident.

Evidence for a scenario (CI/CD, Kubernetes, observability) is loaded by the
graph from the matching fixture files, so triggering one needs no GitHub
credentials.  Ground truth lives in data/ground_truth and is never read here.
"""

import json
from typing import Dict, List

from backend.models import Incident
from backend.tools.data_access import data_loader


def list_scenarios() -> List[Dict[str, str]]:
    incidents_dir = data_loader.data_dir / "incidents"
    scenarios = []
    for path in sorted(incidents_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        scenarios.append({
            "scenario_id": path.stem,
            "title": data.get("title", path.stem),
            "severity": data.get("severity", ""),
            "service_name": data.get("service_name", ""),
            "namespace": data.get("namespace", ""),
        })
    return scenarios


def load_scenario_incident(scenario_id: str) -> Incident:
    data = data_loader.load_incident_data(scenario_id)
    if not data:
        raise KeyError(scenario_id)
    return Incident(**data)
