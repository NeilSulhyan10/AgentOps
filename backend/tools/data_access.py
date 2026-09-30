from typing import Dict, List, Any, Optional
from backend.models import Incident, Evidence, AgentType, EvidenceType
import json
from pathlib import Path
from backend.config import settings


class DataLoader:
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = settings.data_dir
        self.data_dir = Path(data_dir)
    def load_incident_data(self, incident_id: str) -> Dict[str, Any]:
        incident_file = self.data_dir / "incidents" / f"{incident_id}.json"
        if incident_file.exists():
            with open(incident_file) as f:
                return json.load(f)
        return {}

    def load_cicd_data(self, incident_id: str) -> Dict[str, Any]:
        cicd_file = self.data_dir / "cicd" / f"{incident_id}.json"
        if cicd_file.exists():
            with open(cicd_file) as f:
                return json.load(f)
        return {}

    def load_kubernetes_data(self, incident_id: str) -> Dict[str, Any]:
        k8s_file = self.data_dir / "kubernetes" / f"{incident_id}.json"
        if k8s_file.exists():
            with open(k8s_file) as f:
                return json.load(f)
        return {}

    def load_observability_data(self, incident_id: str) -> Dict[str, Any]:
        obs_file = self.data_dir / "observability" / f"{incident_id}.json"
        if obs_file.exists():
            with open(obs_file) as f:
                return json.load(f)
        return {}


data_loader = DataLoader()


def get_cicd_evidence(incident: Incident) -> List[Evidence]:
    data = data_loader.load_cicd_data(incident.incident_id)
    evidence = []

    if "deployments" in data:
        for dep in data["deployments"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type=AgentType.CICD,
                evidence_type=EvidenceType.DEPLOYMENT,
                description=f"Deployment {dep.get('deployment_id', 'unknown')} at {dep.get('timestamp', 'unknown')}",
                raw_data=dep,
                confidence=0.8,
                source="cicd_fixture"
            ))

    if "code_changes" in data:
        for change in data["code_changes"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type=AgentType.CICD,
                evidence_type=EvidenceType.CODE_CHANGE,
                description=f"Code change in {change.get('file', 'unknown')}: {change.get('description', 'unknown')}",
                raw_data=change,
                confidence=0.7,
                source="cicd_fixture"
            ))

    if "config_changes" in data:
        for change in data["config_changes"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type=AgentType.CICD,
                evidence_type=EvidenceType.CONFIG_CHANGE,
                description=f"Config change: {change.get('key', 'unknown')} = {change.get('new_value', 'unknown')}",
                raw_data=change,
                confidence=0.85,
                source="cicd_fixture"
            ))

    if "dependency_changes" in data:
        for dep in data["dependency_changes"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type=AgentType.CICD,
                evidence_type=EvidenceType.DEPENDENCY_CHANGE,
                description=f"Dependency change: {dep.get('name', 'unknown')} {dep.get('old_version', '?')} -> {dep.get('new_version', '?')}",
                raw_data=dep,
                confidence=0.75,
                source="cicd_fixture"
            ))

    return evidence


def get_kubernetes_evidence(incident: Incident) -> List[Evidence]:
    data = data_loader.load_kubernetes_data(incident.incident_id)
    evidence = []

    if "pods" in data:
        for pod in data["pods"]:
            if "exit_code" in pod:
                evidence.append(Evidence(
                    investigation_id="",
                    agent_type=AgentType.KUBERNETES,
                    evidence_type=EvidenceType.POD_EXIT_CODE,
                    description=f"Pod {pod.get('name', 'unknown')} exited with code {pod['exit_code']}",
                    raw_data=pod,
                    confidence=0.9,
                    source="kubernetes_fixture"
                ))

            if "restart_count" in pod:
                evidence.append(Evidence(
                    investigation_id="",
                    agent_type=AgentType.KUBERNETES,
                    evidence_type=EvidenceType.POD_RESTART_COUNT,
                    description=f"Pod {pod.get('name', 'unknown')} restarted {pod['restart_count']} times",
                    raw_data=pod,
                    confidence=0.85,
                    source="kubernetes_fixture"
                ))

            if "events" in pod:
                for event in pod["events"]:
                    evidence.append(Evidence(
                        investigation_id="",
                        agent_type=AgentType.KUBERNETES,
                        evidence_type=EvidenceType.POD_EVENT,
                        description=f"Pod {pod.get('name', 'unknown')} event: {event.get('reason', 'unknown')} - {event.get('message', 'unknown')}",
                        raw_data=event,
                        confidence=0.8,
                        source="kubernetes_fixture"
                    ))

            if "memory_usage" in pod and "memory_limit" in pod:
                usage = pod["memory_usage"]
                limit = pod["memory_limit"]
                evidence.append(Evidence(
                    investigation_id="",
                    agent_type=AgentType.KUBERNETES,
                    evidence_type=EvidenceType.RESOURCE_USAGE,
                    description=f"Pod {pod.get('name', 'unknown')} memory usage: {usage} / {limit}",
                    raw_data={"usage": usage, "limit": limit, "pod": pod.get('name')},
                    confidence=0.9,
                    source="kubernetes_fixture"
                ))
                evidence.append(Evidence(
                    investigation_id="",
                    agent_type=AgentType.KUBERNETES,
                    evidence_type=EvidenceType.RESOURCE_LIMIT,
                    description=f"Pod {pod.get('name', 'unknown')} memory limit: {limit}",
                    raw_data={"limit": limit, "pod": pod.get('name')},
                    confidence=0.9,
                    source="kubernetes_fixture"
                ))

    return evidence


def get_observability_evidence(incident: Incident) -> List[Evidence]:
    data = data_loader.load_observability_data(incident.incident_id)
    evidence = []

    if "latency" in data:
        lat = data["latency"]
        evidence.append(Evidence(
            investigation_id="",
            agent_type=AgentType.OBSERVABILITY,
            evidence_type=EvidenceType.LATENCY,
            description=f"P95 latency: {lat.get('p95', 'unknown')}, P99 latency: {lat.get('p99', 'unknown')}",
            raw_data=lat,
            confidence=0.85,
            source="observability_fixture"
        ))

    if "error_rate" in data:
        err = data["error_rate"]
        evidence.append(Evidence(
            investigation_id="",
            agent_type=AgentType.OBSERVABILITY,
            evidence_type=EvidenceType.ERROR_RATE,
            description=f"Error rate: {err.get('rate', 'unknown')}% ({err.get('count', 'unknown')} errors)",
            raw_data=err,
            confidence=0.9,
            source="observability_fixture"
        ))

    if "logs" in data:
        for log in data["logs"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type=AgentType.OBSERVABILITY,
                evidence_type=EvidenceType.LOG,
                description=f"Log: {log.get('message', 'unknown')}",
                raw_data=log,
                confidence=0.7,
                source="observability_fixture"
            ))

    if "stack_traces" in data:
        for trace in data["stack_traces"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type=AgentType.OBSERVABILITY,
                evidence_type=EvidenceType.STACK_TRACE,
                description=f"Stack trace: {trace.get('error', 'unknown')}",
                raw_data=trace,
                confidence=0.85,
                source="observability_fixture"
            ))

    if "traces" in data:
        for trace in data["traces"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type=AgentType.OBSERVABILITY,
                evidence_type=EvidenceType.TRACE,
                description=f"Trace {trace.get('trace_id', 'unknown')}: {trace.get('duration', 'unknown')}ms",
                raw_data=trace,
                confidence=0.8,
                source="observability_fixture"
            ))

    return evidence