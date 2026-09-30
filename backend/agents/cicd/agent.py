from typing import List, Dict, Any
from backend.models import (
    Incident,
    AgentFinding,
    AgentType,
    HypothesisType,
    Evidence
)
# from backend.tools.data_access import get_cicd_evidence


class CICDAgent:
    def __init__(self):
        self.agent_type = AgentType.CICD

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
                "finding": "No CI/CD evidence found for this incident",
                "evidence": [],
                "confidence": 0.1,
                "reasoning": "No deployment or configuration data available"
            }

        deployment_evidence = [e for e in evidence if e.evidence_type == "deployment"]
        config_evidence = [e for e in evidence if e.evidence_type == "config_change"]
        code_evidence = [e for e in evidence if e.evidence_type == "code_change"]
        dep_evidence = [e for e in evidence if e.evidence_type == "dependency_change"]

        findings = []
        evidence_refs = []
        confidence = 0.5

        if deployment_evidence:
            dep = deployment_evidence[0]
            findings.append(f"Recent deployment detected: {dep.description}")
            evidence_refs.append(dep.description)
            confidence = max(confidence, 0.7)

        if config_evidence:
            for cfg in config_evidence:
                findings.append(f"Configuration change detected: {cfg.description}")
                evidence_refs.append(cfg.description)
                confidence = max(confidence, 0.85)

        if code_evidence:
            for code in code_evidence:
                findings.append(f"Code change detected: {code.description}")
                evidence_refs.append(code.description)
                confidence = max(confidence, 0.7)

        if dep_evidence:
            for dep in dep_evidence:
                findings.append(f"Dependency change detected: {dep.description}")
                evidence_refs.append(dep.description)
                confidence = max(confidence, 0.75)

        if config_evidence and any("memory" in c.description.lower() or "limit" in c.description.lower() for c in config_evidence):
            hypothesis = HypothesisType.DEPLOYMENT_INDUCED_FAILURE
            finding_text = "Configuration change modified resource limits, likely causing deployment-induced failure"
            confidence = max(confidence, 0.9)
        elif deployment_evidence:
            hypothesis = HypothesisType.DEPLOYMENT_INDUCED_FAILURE
            finding_text = "Recent deployment correlates with incident timing"
            confidence = max(confidence, 0.8)
        elif code_evidence:
            hypothesis = HypothesisType.APPLICATION_ERROR
            finding_text = "Code changes detected that may have introduced regression"
            confidence = max(confidence, 0.7)
        elif dep_evidence:
            hypothesis = HypothesisType.DEPENDENCY_ISSUE
            finding_text = "Dependency version changes detected"
            confidence = max(confidence, 0.75)
        else:
            hypothesis = HypothesisType.UNKNOWN
            finding_text = "CI/CD evidence found but no clear pattern identified"

        return {
            "hypothesis": hypothesis,
            "finding": finding_text,
            "evidence": evidence_refs,
            "confidence": round(confidence, 2),
            "reasoning": "; ".join(findings) if findings else "No specific findings"
        }