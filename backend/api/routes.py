from fastapi import APIRouter, HTTPException, status, WebSocket, WebSocketDisconnect
from typing import List, Optional
from backend.models import (
    Incident,
    InvestigationState,
    InvestigationRequest,
    InvestigationResponse,
    InvestigationStatusResponse,
    InvestigationStatus,
    AgentFinding,
    Evidence,
    RootCauseAnalysis,
    RemediationRecommendation
)
from backend.services.investigation_service import investigation_service
from backend.services.scenarios import list_scenarios, load_scenario_incident
from backend.orchestrator.state import mongo_state_manager
from backend.api.websocket import investigation_websocket


router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("", response_model=InvestigationResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(request: InvestigationRequest):
    incident = request.incident
    investigation = await investigation_service.start_investigation(incident)

    return InvestigationResponse(
        investigation_id=investigation.investigation_id,
        status=investigation.investigation_status,
        message="Investigation started — processing in background"
    )


@router.get("", response_model=List[InvestigationStatusResponse])
async def list_incidents(status_filter: Optional[InvestigationStatus] = None):
    investigations = await investigation_service.list_investigations(status_filter)

    return [
        InvestigationStatusResponse(
            investigation_id=inv.investigation_id,
            incident_id=inv.incident_id,
            incident_title=inv.incident.title if inv.incident else inv.incident_id,
            service_name=inv.incident.service_name if inv.incident else "",
            namespace=inv.incident.namespace if inv.incident else "",
            status=inv.investigation_status,
            current_hypothesis=inv.current_hypothesis,
            overall_confidence=inv.overall_confidence,
            iteration_count=inv.iteration_count,
            agents_invoked=inv.agents_invoked,
            evidence_count=len(inv.evidence),
            created_at=inv.created_at,
            updated_at=inv.updated_at,
            completed_at=inv.completed_at
        )
        for inv in investigations
    ]


@router.get("/{incident_id}", response_model=InvestigationStatusResponse)
async def get_incident(incident_id: str):
    investigations = await investigation_service.list_investigations()
    investigation = next((inv for inv in investigations if inv.incident_id == incident_id), None)

    if not investigation:
        raise HTTPException(status_code=404, detail="Incident not found")

    return InvestigationStatusResponse(
        investigation_id=investigation.investigation_id,
        incident_id=investigation.incident_id,
        incident_title=investigation.incident.title if investigation.incident else investigation.incident_id,
        service_name=investigation.incident.service_name if investigation.incident else "",
        namespace=investigation.incident.namespace if investigation.incident else "",
        status=investigation.investigation_status,
        current_hypothesis=investigation.current_hypothesis,
        overall_confidence=investigation.overall_confidence,
        iteration_count=investigation.iteration_count,
        agents_invoked=investigation.agents_invoked,
        evidence_count=len(investigation.evidence),
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
        completed_at=investigation.completed_at
    )


scenario_router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@scenario_router.get("")
async def get_scenarios():
    return {"scenarios": list_scenarios()}


@scenario_router.post("/trigger-all", response_model=List[InvestigationResponse], status_code=status.HTTP_201_CREATED)
async def trigger_all_scenarios():
    responses = []
    for scenario in list_scenarios():
        incident = load_scenario_incident(scenario["scenario_id"])
        investigation = await investigation_service.start_investigation(incident, evidence=[])
        responses.append(InvestigationResponse(
            investigation_id=investigation.investigation_id,
            status=investigation.investigation_status,
            message=f"Scenario {scenario['scenario_id']} started",
        ))
    return responses


@scenario_router.post("/{scenario_id}/trigger", response_model=InvestigationResponse, status_code=status.HTTP_201_CREATED)
async def trigger_scenario(scenario_id: str):
    try:
        incident = load_scenario_incident(scenario_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario_id}")
    investigation = await investigation_service.start_investigation(incident, evidence=[])
    return InvestigationResponse(
        investigation_id=investigation.investigation_id,
        status=investigation.investigation_status,
        message=f"Scenario {scenario_id} started — processing in background",
    )


investigation_router = APIRouter(prefix="/investigations", tags=["investigations"])


@investigation_router.delete("/{investigation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_investigation(investigation_id: str):
    deleted = await mongo_state_manager.delete_state(investigation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Investigation not found")


@investigation_router.get("/{investigation_id}", response_model=InvestigationState)
async def get_investigation(investigation_id: str):
    investigation = await investigation_service.get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return investigation


@investigation_router.get("/{investigation_id}/timeline")
async def get_investigation_timeline(investigation_id: str):
    investigation = await investigation_service.get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    timeline = []

    for finding in investigation.agent_findings:
        agent_type_str = finding.agent_type if isinstance(finding.agent_type, str) else finding.agent_type
        hypothesis_str = finding.hypothesis if isinstance(finding.hypothesis, str) else finding.hypothesis
        timeline.append({
            "type": "agent_finding",
            "iteration": finding.iteration,
            "agent": agent_type_str,
            "hypothesis": hypothesis_str,
            "finding": finding.finding,
            "confidence": finding.confidence,
            "evidence": finding.evidence,
            "reasoning": finding.reasoning,
            "timestamp": finding.timestamp.isoformat()
        })

    for decision in investigation.routing_decisions:
        selected_agent_str = decision.selected_agent if isinstance(decision.selected_agent, str) else decision.selected_agent
        agents_invoked_str = [a if isinstance(a, str) else a for a in decision.agents_invoked]
        timeline.append({
            "type": "routing_decision",
            "iteration": decision.iteration,
            "selected_agent": selected_agent_str,
            "reasoning": decision.reasoning,
            "evidence_gaps": decision.evidence_gaps,
            "agents_invoked": agents_invoked_str,
            "timestamp": decision.timestamp.isoformat()
        })

    for conf in investigation.confidence_history:
        agent_confidences_str = {k if isinstance(k, str) else k.value: v for k, v in conf.agent_confidences.items()}
        timeline.append({
            "type": "confidence_update",
            "iteration": conf.iteration,
            "overall_confidence": conf.overall_confidence,
            "agent_confidences": agent_confidences_str,
            "threshold": conf.threshold,
            "is_sufficient": conf.is_sufficient,
            "timestamp": conf.timestamp.isoformat()
        })

    for review in investigation.critic_reviews:
        timeline.append({
            "type": "critic_review",
            "round": review.round,
            "verdict": review.verdict,
            "hypothesis": review.assessed_hypothesis if isinstance(review.assessed_hypothesis, str) else review.assessed_hypothesis.value,
            "concerns": review.concerns,
            "missing_checks": review.missing_checks,
            "suggested_agent": review.suggested_agent,
            "confidence": review.confidence,
            "reasoning": review.reasoning,
            "timestamp": review.timestamp.isoformat()
        })

    return {"timeline": sorted(timeline, key=lambda x: x["timestamp"])}


@investigation_router.get("/{investigation_id}/critic")
async def get_critic_reviews(investigation_id: str):
    investigation = await investigation_service.get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return {"reviews": [r.model_dump(mode="json") for r in investigation.critic_reviews]}


@investigation_router.get("/{investigation_id}/evidence")
async def get_investigation_evidence(investigation_id: str):
    investigation = await investigation_service.get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return {
        "evidence": [
            {
                "evidence_id": e.evidence_id,
                "agent_type": e.agent_type if isinstance(e.agent_type, str) else e.agent_type,
                "evidence_type": e.evidence_type if isinstance(e.evidence_type, str) else e.evidence_type,
                "description": e.description,
                "confidence": e.confidence,
                "raw_data": e.raw_data,
                "timestamp": e.timestamp.isoformat()
            }
            for e in investigation.evidence
        ]
    }


@investigation_router.get("/{investigation_id}/root-cause")
async def get_root_cause(investigation_id: str):
    investigation = await investigation_service.get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    if not investigation.root_cause:
        raise HTTPException(status_code=404, detail="Root cause analysis not yet generated")

    rca = investigation.root_cause
    root_cause_type_str = rca.root_cause_type if isinstance(rca.root_cause_type, str) else rca.root_cause_type.value
    agents_consulted_str = [a if isinstance(a, str) else a for a in rca.agents_consulted]
    return {
        "rca_id": rca.rca_id,
        "investigation_id": rca.investigation_id,
        "incident_id": rca.incident_id,
        "root_cause": rca.root_cause,
        "root_cause_type": root_cause_type_str,
        "contributing_factors": rca.contributing_factors,
        "evidence": rca.evidence,
        "agents_consulted": agents_consulted_str,
        "overall_confidence": rca.overall_confidence,
        "investigation_timeline": rca.investigation_timeline,
        "created_at": rca.created_at.isoformat()
    }


@investigation_router.get("/{investigation_id}/remediation")
async def get_remediation(investigation_id: str):
    investigation = await investigation_service.get_investigation(investigation_id)

    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    if not investigation.remediation:
        raise HTTPException(status_code=404, detail="Remediation not yet generated")

    rem = investigation.remediation
    return {
        "remediation_id": rem.remediation_id,
        "investigation_id": rem.investigation_id,
        "rca_id": rem.rca_id,
        "recommendation": rem.recommendation,
        "steps": rem.steps,
        "priority": rem.priority,
        "estimated_effort": rem.estimated_effort,
        "risk_level": rem.risk_level,
        "status": rem.status,
        "created_at": rem.created_at.isoformat()
    }


# WebSocket endpoint for real-time investigation updates
@investigation_router.websocket("/{investigation_id}/ws")
async def investigation_websocket_route(websocket: WebSocket, investigation_id: str):
    """WebSocket endpoint for real-time investigation updates."""
    await investigation_websocket(websocket, investigation_id)
