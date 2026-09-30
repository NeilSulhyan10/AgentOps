from typing import List, Dict, Any
from backend.models import (
    Incident,
    AgentFinding,
    AgentType,
    HypothesisType,
    Evidence
)
# from backend.tools.data_access import get_observability_evidence


class ObservabilityAgent:
    def __init__(self):
        self.agent_type = AgentType.OBSERVABILITY

    def investigate(self, incident: Incident, existing_evidence: List[Evidence]) -> AgentFinding:
        # Use the passed evidence instead of loading from fixtures
        finding = self._analyze_evidence(incident, existing_evidence)

        return AgentFinding(
            investigation_id="",
            agent_type=self.agent_type,
            hypothesis=finding["hypothesis"],
            finding=finding["finding"],
            evidence=finding["evidence"],
            confidence=finding["confidence"],
            reasoning=finding["reasoning"],
            iteration=0
        )

    def _analyze_evidence(self, incident: Incident, evidence: List[Evidence]) -> Dict[str, Any]:
        if not evidence:
            return {
                "hypothesis": HypothesisType.UNKNOWN,
                "finding": "No observability evidence found for this incident",
                "evidence": [],
                "confidence": 0.1,
                "reasoning": "No metrics, logs, or traces available"
            }

        latency_evidence = [e for e in evidence if e.evidence_type == "latency"]
        error_evidence = [e for e in evidence if e.evidence_type == "error_rate"]
        log_evidence = [e for e in evidence if e.evidence_type == "log"]
        trace_evidence = [e for e in evidence if e.evidence_type == "trace"]
        stack_evidence = [e for e in evidence if e.evidence_type == "stack_trace"]

        findings = []
        evidence_refs = []
        confidence = 0.5

        for lat in latency_evidence:
            p99 = lat.raw_data.get("p99", 0)
            p95 = lat.raw_data.get("p95", 0)
            if isinstance(p99, (int, float)) and p99 > 2000:
                findings.append(f"High P99 latency: {p99}ms")
                evidence_refs.append(lat.description)
                confidence = max(confidence, 0.85)
            elif isinstance(p95, (int, float)) and p95 > 1000:
                findings.append(f"Elevated P95 latency: {p95}ms")
                evidence_refs.append(lat.description)
                confidence = max(confidence, 0.75)

        for err in error_evidence:
            rate = err.raw_data.get("rate", 0)
            if isinstance(rate, (int, float)) and rate > 10:
                findings.append(f"High error rate: {rate}%")
                evidence_refs.append(err.description)
                confidence = max(confidence, 0.9)
            elif isinstance(rate, (int, float)) and rate > 1:
                findings.append(f"Elevated error rate: {rate}%")
                evidence_refs.append(err.description)
                confidence = max(confidence, 0.7)

        for log in log_evidence[:5]:
            findings.append(f"Log entry: {log.description}")
            evidence_refs.append(log.description)

        for trace in trace_evidence:
            duration = trace.raw_data.get("duration", 0)
            if isinstance(duration, (int, float)) and duration > 5000:
                findings.append(f"Slow trace detected: {duration}ms")
                evidence_refs.append(trace.description)
                confidence = max(confidence, 0.8)

        for stack in stack_evidence:
            findings.append(f"Stack trace: {stack.description}")
            evidence_refs.append(stack.description)
            confidence = max(confidence, 0.85)

        has_high_latency = any(
            isinstance(e.raw_data.get("p99", 0), (int, float)) and e.raw_data.get("p99", 0) > 2000
            for e in latency_evidence
        )
        has_any_latency = any(
            isinstance(e.raw_data.get("p99", 0), (int, float)) and e.raw_data.get("p99", 0) > 0
            for e in latency_evidence
        )
        has_high_errors = any(
            isinstance(e.raw_data.get("rate", 0), (int, float)) and e.raw_data.get("rate", 0) > 10
            for e in error_evidence
        )

        if has_high_latency and has_high_errors:
            hypothesis = HypothesisType.TRAFFIC_INCIDENT
            finding_text = "High latency and error rate indicate traffic-related incident or downstream dependency failure"
            confidence = max(confidence, 0.85)
        elif has_high_errors and has_any_latency:
            hypothesis = HypothesisType.TRAFFIC_INCIDENT
            finding_text = "Elevated latency and high error rate indicate traffic-related incident or downstream dependency failure"
            confidence = max(confidence, 0.85)
        elif has_high_errors:
            hypothesis = HypothesisType.APPLICATION_ERROR
            finding_text = "Elevated error rate suggests application-level issues"
            confidence = max(confidence, 0.8)
        elif has_high_latency:
            hypothesis = HypothesisType.TRAFFIC_INCIDENT
            finding_text = "High latency detected, possible traffic spike or resource contention"
            confidence = max(confidence, 0.75)
        elif stack_evidence:
            hypothesis = HypothesisType.APPLICATION_ERROR
            finding_text = "Application errors detected in stack traces"
            confidence = max(confidence, 0.8)
        else:
            hypothesis = HypothesisType.UNKNOWN
            finding_text = "Observability data shows anomalies but no clear pattern"

        return {
            "hypothesis": hypothesis,
            "finding": finding_text,
            "evidence": evidence_refs,
            "confidence": round(confidence, 2),
            "reasoning": "; ".join(findings) if findings else "No specific findings"
        }