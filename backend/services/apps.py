"""
Apps: the applications AgentOps investigates, derived from the scenario catalogue.

Every scenario (data/incidents/<id>.json) belongs to one app: ``shoplite-S1`` to
``shoplite-S7`` belong to ShopLite; any other scenario belongs to the app named
by its ``service_name``.  Display names and descriptions can be set in
``data/apps.json``; an app missing from that file gets a name made from its key.
"""

import json
from typing import Any, Dict, List, Optional

from backend.services.scenarios import list_scenarios
from backend.tools.data_access import data_loader


def app_key(scenario_id: str, service_name: str = "") -> str:
    if scenario_id.startswith("shoplite-"):
        return "shoplite"
    return service_name or "other"


def _overrides() -> Dict[str, Dict[str, str]]:
    path = data_loader.data_dir / "apps.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def expected_root_cause(scenario_id: str) -> Optional[str]:
    """Ground truth, shown in the developer UI only; the agents never read it."""
    path = data_loader.data_dir / "ground_truth" / f"{scenario_id}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("root_cause_type") if path.exists() else None
    except (OSError, json.JSONDecodeError):
        return None


def list_apps() -> List[Dict[str, Any]]:
    """[{key, name, description, scenarios: [{scenario_id, title, severity, expected_root_cause}]}], ShopLite first."""
    overrides = _overrides()
    apps: Dict[str, Dict[str, Any]] = {}
    for scenario in list_scenarios():
        key = app_key(scenario["scenario_id"], scenario.get("service_name", ""))
        info = overrides.get(key, {})
        app = apps.setdefault(key, {
            "key": key,
            "name": info.get("name") or key.replace("-", " ").replace("_", " ").title(),
            "description": info.get("description", ""),
            "scenarios": [],
        })
        app["scenarios"].append({
            "scenario_id": scenario["scenario_id"], "title": scenario["title"], "severity": scenario["severity"],
            "expected_root_cause": expected_root_cause(scenario["scenario_id"]),
        })
    return sorted(apps.values(), key=lambda a: (a["key"] != "shoplite", a["name"]))


def get_app(key: str) -> Optional[Dict[str, Any]]:
    return next((a for a in list_apps() if a["key"] == key), None)
