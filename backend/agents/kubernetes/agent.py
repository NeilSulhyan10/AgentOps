from typing import List, Dict, Any
from backend.models import (
    Incident,
    AgentFinding,
    AgentType,
    HypothesisType,
    Evidence
)
# from backend.tools.data_access import get_kubernetes_evidence


class KubernetesAgent:
    def __init__(self):
        self.agent_type = AgentType.KUBERNETES

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
                "finding": "No Kubernetes evidence found for this incident",
                "evidence": [],
                "confidence": 0.1,
                "reasoning": "No pod or resource data available"
            }

        exit_code_evidence = [e for e in evidence if e.evidence_type == "pod_exit_code"]
        restart_evidence = [e for e in evidence if e.evidence_type == "pod_restart_count"]
        event_evidence = [e for e in evidence if e.evidence_type == "pod_event"]
        usage_evidence = [e for e in evidence if e.evidence_type == "resource_usage"]
        limit_evidence = [e for e in evidence if e.evidence_type == "resource_limit"]

        findings = []
        evidence_refs = []
        confidence = 0.5

        oom_killed = False
        for exc in exit_code_evidence:
            code = exc.raw_data.get("exit_code", 0)
            if code == 137:
                findings.append(f"Pod OOMKilled (exit code 137): {exc.description}")
                evidence_refs.append(exc.description)
                oom_killed = True
                confidence = max(confidence, 0.95)
            elif code != 0:
                findings.append(f"Pod exited with code {code}: {exc.description}")
                evidence_refs.append(exc.description)
                confidence = max(confidence, 0.8)

        for rst in restart_evidence:
            count = rst.raw_data.get("restart_count", 0)
            if count > 5:
                findings.append(f"High restart count ({count}): {rst.description}")
                evidence_refs.append(rst.description)
                confidence = max(confidence, 0.85)

        for evt in event_evidence:
            reason = evt.raw_data.get("reason", "")
            if reason in ["OOMKilling", "OutOfMemory", "Killing"]:
                findings.append(f"OOM event detected: {evt.description}")
                evidence_refs.append(evt.description)
                oom_killed = True
                confidence = max(confidence, 0.95)

        for usage in usage_evidence:
            usage_val = usage.raw_data.get("usage", "")
            limit_val = usage.raw_data.get("limit", "")
            findings.append(f"Resource usage near limit: {usage.description}")
            evidence_refs.append(usage.description)
            if "Mi" in str(usage_val) and "Gi" in str(limit_val):
                try:
                    usage_num = float(usage_val.replace("Mi", ""))
                    limit_num = float(limit_val.replace("Gi", "")) * 1024
                    if usage_num / limit_num > 0.9:
                        findings.append(f"Memory usage at {usage_num/limit_num*100:.0f}% of limit")
                        confidence = max(confidence, 0.9)
                except:
                    pass

        if oom_killed:
            hypothesis = HypothesisType.KUBERNETES_OOM
            finding_text = "Pod was OOMKilled due to memory exhaustion"
            confidence = max(confidence, 0.92)
        elif restart_evidence and any(r.raw_data.get("restart_count", 0) > 3 for r in restart_evidence):
            hypothesis = HypothesisType.KUBERNETES_OOM
            finding_text = "Pod experiencing frequent restarts, possible resource pressure"
            confidence = max(confidence, 0.8)
        elif event_evidence:
            hypothesis = HypothesisType.KUBERNETES_OOM
            finding_text = "Kubernetes events indicate pod issues"
            confidence = max(confidence, 0.7)
        else:
            hypothesis = HypothesisType.UNKNOWN
            finding_text = "Kubernetes evidence found but no clear failure pattern"

        return {
            "hypothesis": hypothesis,
            "finding": finding_text,
            "evidence": evidence_refs,
            "confidence": round(confidence, 2),
            "reasoning": "; ".join(findings) if findings else "No specific findings"
        }