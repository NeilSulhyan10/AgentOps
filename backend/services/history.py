"""Run history: every investigation of an incident, newest first.  Re-running an incident adds a run; nothing is overwritten."""

from typing import Any, Dict, List, Optional

from backend.models.mongodb import InvestigationDoc, RootCauseAnalysisDoc


async def runs_by_incident(incident_ids: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
    """{incident_id: [run, ...]} for the given incidents (all when None)."""
    query = InvestigationDoc.find({"incident_id": {"$in": incident_ids}}) if incident_ids is not None else InvestigationDoc.find()
    docs = await query.sort(-InvestigationDoc.created_at).to_list()
    causes = {
        rca.investigation_id: rca.root_cause_type
        for rca in await RootCauseAnalysisDoc.find({"investigation_id": {"$in": [d.investigation_id for d in docs]}}).to_list()
    }
    runs: Dict[str, List[Dict[str, Any]]] = {}
    for d in docs:
        status = getattr(d.investigation_status, "value", d.investigation_status)
        cause = causes.get(d.investigation_id)
        runs.setdefault(d.incident_id, []).append({
            "investigation_id": d.investigation_id,
            "incident_id": d.incident_id,
            "status": status,
            "root_cause_type": getattr(cause, "value", cause),
            "confidence": d.overall_confidence,
            "agents_invoked": list(dict.fromkeys(d.agents_invoked)),
            "iterations": d.iteration_count,
            "created_at": d.created_at.isoformat(),
            "completed_at": d.completed_at.isoformat() if d.completed_at else None,
            "duration_s": round((d.completed_at - d.created_at).total_seconds(), 1) if d.completed_at else None,
        })
    return runs
