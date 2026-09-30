from typing import Dict, List, Any, Optional
from datetime import datetime
from backend.models import (
    InvestigationState, Incident, IncidentSeverity, IncidentStatus,
    AgentType, HypothesisType, InvestigationStatus,
    Evidence, AgentFinding, RoutingDecision, ConfidenceEntry,
    RootCauseAnalysis, RemediationRecommendation, EvidenceType
)
from backend.models.mongodb import (
    InvestigationDoc, IncidentDoc, EvidenceDoc, AgentFindingDoc,
    RoutingDecisionDoc, ConfidenceEntryDoc, RootCauseAnalysisDoc, RemediationDoc
)
import json


class MongoStateManager:
    def __init__(self):
        pass

    def _incident_to_doc(self, incident: Incident) -> IncidentDoc:
        return IncidentDoc(
            incident_id=incident.incident_id,
            title=incident.title,
            description=incident.description,
            severity=incident.severity,
            status=incident.status,
            source=incident.source,
            service_name=incident.service_name,
            namespace=incident.namespace,
            started_at=incident.started_at,
            detected_at=incident.detected_at,
            metadata=incident.metadata,
            tags=incident.tags,
        )

    def _doc_to_incident(self, doc: IncidentDoc) -> Incident:
        return Incident(
            incident_id=doc.incident_id,
            title=doc.title,
            description=doc.description,
            severity=doc.severity,
            status=doc.status,
            source=doc.source,
            service_name=doc.service_name,
            namespace=doc.namespace,
            started_at=doc.started_at,
            detected_at=doc.detected_at,
            metadata=doc.metadata,
            tags=doc.tags,
        )

    def _evidence_to_doc(self, ev: Evidence, investigation_id: str) -> EvidenceDoc:
        return EvidenceDoc(
            evidence_id=ev.evidence_id,
            investigation_id=investigation_id,
            agent_type=ev.agent_type,
            evidence_type=ev.evidence_type,
            description=ev.description,
            raw_data=ev.raw_data,
            confidence=ev.confidence,
            timestamp=ev.timestamp,
            source=ev.source,
        )

    def _doc_to_evidence(self, doc: EvidenceDoc) -> Evidence:
        return Evidence(
            evidence_id=doc.evidence_id,
            investigation_id=doc.investigation_id,
            agent_type=doc.agent_type,
            evidence_type=doc.evidence_type,
            description=doc.description,
            raw_data=doc.raw_data,
            confidence=doc.confidence,
            timestamp=doc.timestamp,
            source=doc.source,
        )

    def _finding_to_doc(self, finding: AgentFinding, investigation_id: str) -> AgentFindingDoc:
        return AgentFindingDoc(
            finding_id=finding.finding_id,
            investigation_id=investigation_id,
            agent_type=finding.agent_type,
            hypothesis=finding.hypothesis,
            finding=finding.finding,
            evidence=finding.evidence,
            confidence=finding.confidence,
            reasoning=finding.reasoning,
            timestamp=finding.timestamp,
            iteration=finding.iteration,
        )

    def _doc_to_finding(self, doc: AgentFindingDoc) -> AgentFinding:
        return AgentFinding(
            finding_id=doc.finding_id,
            investigation_id=doc.investigation_id,
            agent_type=doc.agent_type,
            hypothesis=doc.hypothesis,
            finding=doc.finding,
            evidence=doc.evidence,
            confidence=doc.confidence,
            reasoning=doc.reasoning,
            timestamp=doc.timestamp,
            iteration=doc.iteration,
        )

    def _decision_to_doc(self, decision: RoutingDecision, investigation_id: str) -> RoutingDecisionDoc:
        return RoutingDecisionDoc(
            decision_id=decision.decision_id,
            investigation_id=investigation_id,
            iteration=decision.iteration,
            current_hypothesis=decision.current_hypothesis,
            evidence_gaps=decision.evidence_gaps,
            agents_invoked=decision.agents_invoked,
            available_agents=decision.available_agents,
            selected_agent=decision.selected_agent,
            reasoning=decision.reasoning,
            timestamp=decision.timestamp,
        )

    def _doc_to_decision(self, doc: RoutingDecisionDoc) -> RoutingDecision:
        return RoutingDecision(
            decision_id=doc.decision_id,
            investigation_id=doc.investigation_id,
            iteration=doc.iteration,
            current_hypothesis=doc.current_hypothesis,
            evidence_gaps=doc.evidence_gaps,
            agents_invoked=doc.agents_invoked,
            available_agents=doc.available_agents,
            selected_agent=doc.selected_agent,
            reasoning=doc.reasoning,
            timestamp=doc.timestamp,
        )

    def _confidence_to_doc(self, entry: ConfidenceEntry, investigation_id: str) -> ConfidenceEntryDoc:
        return ConfidenceEntryDoc(
            entry_id=entry.entry_id,
            investigation_id=investigation_id,
            iteration=entry.iteration,
            agent_confidences=entry.agent_confidences,
            overall_confidence=entry.overall_confidence,
            threshold=entry.threshold,
            is_sufficient=entry.is_sufficient,
            timestamp=entry.timestamp,
        )

    def _doc_to_confidence(self, doc: ConfidenceEntryDoc) -> ConfidenceEntry:
        return ConfidenceEntry(
            entry_id=doc.entry_id,
            investigation_id=doc.investigation_id,
            iteration=doc.iteration,
            agent_confidences=doc.agent_confidences,
            overall_confidence=doc.overall_confidence,
            threshold=doc.threshold,
            is_sufficient=doc.is_sufficient,
            timestamp=doc.timestamp,
        )

    def _rca_to_doc(self, rca: RootCauseAnalysis) -> RootCauseAnalysisDoc:
        return RootCauseAnalysisDoc(
            rca_id=rca.rca_id,
            investigation_id=rca.investigation_id,
            incident_id=rca.incident_id,
            root_cause=rca.root_cause,
            root_cause_type=rca.root_cause_type,
            contributing_factors=rca.contributing_factors,
            evidence=rca.evidence,
            agents_consulted=rca.agents_consulted,
            overall_confidence=rca.overall_confidence,
            investigation_timeline=rca.investigation_timeline,
            created_at=rca.created_at,
        )

    def _doc_to_rca(self, doc: RootCauseAnalysisDoc) -> RootCauseAnalysis:
        return RootCauseAnalysis(
            rca_id=doc.rca_id,
            investigation_id=doc.investigation_id,
            incident_id=doc.incident_id,
            root_cause=doc.root_cause,
            root_cause_type=doc.root_cause_type,
            contributing_factors=doc.contributing_factors,
            evidence=doc.evidence,
            agents_consulted=doc.agents_consulted,
            overall_confidence=doc.overall_confidence,
            investigation_timeline=doc.investigation_timeline,
            created_at=doc.created_at,
        )

    def _remediation_to_doc(self, rem: RemediationRecommendation) -> RemediationDoc:
        return RemediationDoc(
            remediation_id=rem.remediation_id,
            investigation_id=rem.investigation_id,
            rca_id=rem.rca_id,
            recommendation=rem.recommendation,
            steps=rem.steps,
            priority=rem.priority,
            estimated_effort=rem.estimated_effort,
            risk_level=rem.risk_level,
            status=rem.status,
            created_at=rem.created_at,
        )

    def _doc_to_remediation(self, doc: RemediationDoc) -> RemediationRecommendation:
        return RemediationRecommendation(
            remediation_id=doc.remediation_id,
            investigation_id=doc.investigation_id,
            rca_id=doc.rca_id,
            recommendation=doc.recommendation,
            steps=doc.steps,
            priority=doc.priority,
            estimated_effort=doc.estimated_effort,
            risk_level=doc.risk_level,
            status=doc.status,
            created_at=doc.created_at,
        )

    def _state_to_doc(self, state: InvestigationState) -> InvestigationDoc:
        evidence_ids = []
        for ev in state.evidence:
            ev.investigation_id = state.investigation_id
            evidence_ids.append(ev.evidence_id)
        
        finding_ids = []
        for f in state.agent_findings:
            f.investigation_id = state.investigation_id
            finding_ids.append(f.finding_id)
        
        decision_ids = []
        for d in state.routing_decisions:
            d.investigation_id = state.investigation_id
            decision_ids.append(d.decision_id)
        
        confidence_ids = []
        for c in state.confidence_history:
            c.investigation_id = state.investigation_id
            confidence_ids.append(c.entry_id)

        return InvestigationDoc(
            investigation_id=state.investigation_id,
            incident_id=state.incident_id,
            current_hypothesis=state.current_hypothesis,
            evidence_ids=evidence_ids,
            finding_ids=finding_ids,
            agents_invoked=state.agents_invoked,
            confidence_scores=state.confidence_scores,
            overall_confidence=state.overall_confidence,
            iteration_count=state.iteration_count,
            max_iterations=state.max_iterations,
            evidence_gaps=state.evidence_gaps,
            investigation_status=state.investigation_status,
            rca_id=state.root_cause.rca_id if state.root_cause else None,
            remediation_id=state.remediation.remediation_id if state.remediation else None,
            routing_decision_ids=decision_ids,
            confidence_entry_ids=confidence_ids,
            created_at=state.created_at,
            updated_at=datetime.utcnow(),
            completed_at=state.completed_at,
        )

    async def _doc_to_state(self, doc: InvestigationDoc) -> InvestigationState:
        print(f"DEBUG _doc_to_state: doc.incident_id = {doc.incident_id}")
        incident_doc = await IncidentDoc.find_one(IncidentDoc.incident_id == doc.incident_id)
        print(f"DEBUG _doc_to_state: incident_doc = {incident_doc}")
        print(f"DEBUG _doc_to_state: incident_doc.incident_id if exists = {incident_doc.incident_id if incident_doc else 'None'}")
        incident = self._doc_to_incident(incident_doc) if incident_doc else None

        evidence = []
        for ev_id in doc.evidence_ids:
            ev_doc = await EvidenceDoc.find_one(EvidenceDoc.evidence_id == ev_id)
            if ev_doc:
                evidence.append(self._doc_to_evidence(ev_doc))

        findings = []
        for f_id in doc.finding_ids:
            f_doc = await AgentFindingDoc.find_one(AgentFindingDoc.finding_id == f_id)
            if f_doc:
                findings.append(self._doc_to_finding(f_doc))

        decisions = []
        for d_id in doc.routing_decision_ids:
            d_doc = await RoutingDecisionDoc.find_one(RoutingDecisionDoc.decision_id == d_id)
            if d_doc:
                decisions.append(self._doc_to_decision(d_doc))

        confidence_history = []
        for c_id in doc.confidence_entry_ids:
            c_doc = await ConfidenceEntryDoc.find_one(ConfidenceEntryDoc.entry_id == c_id)
            if c_doc:
                confidence_history.append(self._doc_to_confidence(c_doc))

        rca = None
        if doc.rca_id:
            rca_doc = await RootCauseAnalysisDoc.find_one(RootCauseAnalysisDoc.rca_id == doc.rca_id)
            if rca_doc:
                rca = self._doc_to_rca(rca_doc)

        remediation = None
        if doc.remediation_id:
            rem_doc = await RemediationDoc.find_one(RemediationDoc.remediation_id == doc.remediation_id)
            if rem_doc:
                remediation = self._doc_to_remediation(rem_doc)

        return InvestigationState(
            investigation_id=doc.investigation_id,
            incident=incident,
            incident_id=doc.incident_id,
            current_hypothesis=doc.current_hypothesis,
            evidence=evidence,
            agent_findings=findings,
            agents_invoked=doc.agents_invoked,
            confidence_scores=doc.confidence_scores,
            overall_confidence=doc.overall_confidence,
            iteration_count=doc.iteration_count,
            max_iterations=doc.max_iterations,
            evidence_gaps=doc.evidence_gaps,
            investigation_status=doc.investigation_status,
            root_cause=rca,
            remediation=remediation,
            routing_decisions=decisions,
            confidence_history=confidence_history,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            completed_at=doc.completed_at,
        )

    async def create_state(self, incident: Incident, max_iterations: int = 5, investigation_state: Optional[InvestigationState] = None) -> InvestigationState:
        incident_doc = self._incident_to_doc(incident)
        print(f"DEBUG create_state: incident_doc.incident_id = {incident_doc.incident_id}")
        try:
            await incident_doc.insert()
            print(f"DEBUG create_state: after incident_doc insert")
        except Exception as e:
            print(f"DEBUG create_state: incident_doc insert failed: {e}")
            raise

        if investigation_state is None:
            state = InvestigationState(
                incident=incident,
                incident_id=incident.incident_id,
                max_iterations=max_iterations,
                investigation_status=InvestigationStatus.PENDING,
            )
        else:
            state = investigation_state
            state.max_iterations = max_iterations
            state.investigation_status = InvestigationStatus.PENDING

        print(f"DEBUG create_state: state.investigation_id = {state.investigation_id}")
        doc = self._state_to_doc(state)
        print(f"DEBUG create_state: doc.investigation_id = {doc.investigation_id}")
        await doc.insert()
        print(f"DEBUG create_state: after insert, doc.investigation_id = {doc.investigation_id}")

        for ev in state.evidence:
            ev.investigation_id = state.investigation_id
            ev_doc = self._evidence_to_doc(ev, state.investigation_id)
            await ev_doc.insert()

        return state

    async def get_state(self, investigation_id: str) -> Optional[InvestigationState]:
        doc = await InvestigationDoc.find_one(InvestigationDoc.investigation_id == investigation_id)
        if not doc:
            return None
        return await self._doc_to_state(doc)

    async def update_state(self, state: InvestigationState) -> InvestigationState:
        # Ensure IncidentDoc exists
        incident_doc = await IncidentDoc.find_one(IncidentDoc.incident_id == state.incident_id)
        if not incident_doc:
            incident_doc = self._incident_to_doc(state.incident)
            await incident_doc.insert()

        doc = await InvestigationDoc.find_one(InvestigationDoc.investigation_id == state.investigation_id)
        if not doc:
            doc = self._state_to_doc(state)
            await doc.insert()
        if not doc:
            doc = self._state_to_doc(state)
            await doc.insert()
        else:
            new_doc = self._state_to_doc(state)
            doc.current_hypothesis = new_doc.current_hypothesis
            doc.evidence_ids = new_doc.evidence_ids
            doc.finding_ids = new_doc.finding_ids
            doc.agents_invoked = new_doc.agents_invoked
            doc.confidence_scores = new_doc.confidence_scores
            doc.overall_confidence = new_doc.overall_confidence
            doc.iteration_count = new_doc.iteration_count
            doc.evidence_gaps = new_doc.evidence_gaps
            doc.investigation_status = new_doc.investigation_status
            doc.rca_id = new_doc.rca_id
            doc.remediation_id = new_doc.remediation_id
            doc.routing_decision_ids = new_doc.routing_decision_ids
            doc.confidence_entry_ids = new_doc.confidence_entry_ids
            doc.updated_at = datetime.utcnow()
            doc.completed_at = new_doc.completed_at
            await doc.save()

        for ev in state.evidence:
            ev.investigation_id = state.investigation_id
            ev_doc = await EvidenceDoc.find_one(EvidenceDoc.evidence_id == ev.evidence_id)
            if not ev_doc:
                ev_doc = self._evidence_to_doc(ev, state.investigation_id)
                await ev_doc.insert()

        for finding in state.agent_findings:
            finding.investigation_id = state.investigation_id
            f_doc = await AgentFindingDoc.find_one(AgentFindingDoc.finding_id == finding.finding_id)
            if not f_doc:
                f_doc = self._finding_to_doc(finding, state.investigation_id)
                await f_doc.insert()

        for decision in state.routing_decisions:
            decision.investigation_id = state.investigation_id
            d_doc = await RoutingDecisionDoc.find_one(RoutingDecisionDoc.decision_id == decision.decision_id)
            if not d_doc:
                d_doc = self._decision_to_doc(decision, state.investigation_id)
                await d_doc.insert()

        for entry in state.confidence_history:
            entry.investigation_id = state.investigation_id
            c_doc = await ConfidenceEntryDoc.find_one(ConfidenceEntryDoc.entry_id == entry.entry_id)
            if not c_doc:
                c_doc = self._confidence_to_doc(entry, state.investigation_id)
                await c_doc.insert()

        if state.root_cause:
            state.root_cause.investigation_id = state.investigation_id
            rca_doc = await RootCauseAnalysisDoc.find_one(RootCauseAnalysisDoc.rca_id == state.root_cause.rca_id)
            if not rca_doc:
                rca_doc = self._rca_to_doc(state.root_cause)
                await rca_doc.insert()

        if state.remediation:
            state.remediation.investigation_id = state.investigation_id
            rem_doc = await RemediationDoc.find_one(RemediationDoc.remediation_id == state.remediation.remediation_id)
            if not rem_doc:
                rem_doc = self._remediation_to_doc(state.remediation)
                await rem_doc.insert()

        return state

    async def delete_state(self, investigation_id: str) -> bool:
        doc = await InvestigationDoc.find_one(InvestigationDoc.investigation_id == investigation_id)
        if doc:
            await doc.delete()
            await EvidenceDoc.find({"investigation_id": investigation_id}).delete()
            await AgentFindingDoc.find({"investigation_id": investigation_id}).delete()
            await RoutingDecisionDoc.find({"investigation_id": investigation_id}).delete()
            await ConfidenceEntryDoc.find({"investigation_id": investigation_id}).delete()
            await RootCauseAnalysisDoc.find({"investigation_id": investigation_id}).delete()
            await RemediationDoc.find({"investigation_id": investigation_id}).delete()
            return True
        return False

    async def list_states(self, status: Optional[InvestigationStatus] = None) -> List[InvestigationState]:
        query = InvestigationDoc.find()
        if status:
            query = query.find(InvestigationDoc.investigation_status == status)
        docs = await query.sort(-InvestigationDoc.created_at).to_list()
        states = []
        for doc in docs:
            states.append(await self._doc_to_state(doc))
        return states


mongo_state_manager = MongoStateManager()

# Alias for backward compatibility with tests
state_manager = mongo_state_manager