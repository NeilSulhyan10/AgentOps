from typing import Dict, List, Any, Optional
from backend.models import Incident, Evidence, EvidenceType
import json
from pathlib import Path
from backend.config import settings
import logging

logger = logging.getLogger(__name__)


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

    def load_kubernetes_data(self, incident_id: str) -> Dict[str, Any]:
        k8s_file = self.data_dir / "kubernetes" / f"{incident_id}.json"
        if k8s_file.exists():
            with open(k8s_file) as f:
                return json.load(f)
        return {}

    def load_cicd_data(self, incident_id: str) -> Dict[str, Any]:
        cicd_file = self.data_dir / "cicd" / f"{incident_id}.json"
        if cicd_file.exists():
            with open(cicd_file) as f:
                return json.load(f)
        return {}

    def load_observability_data(self, incident_id: str) -> Dict[str, Any]:
        obs_file = self.data_dir / "observability" / f"{incident_id}.json"
        if obs_file.exists():
            with open(obs_file) as f:
                return json.load(f)
        return {}


data_loader = DataLoader()


async def get_cicd_evidence_from_github(incident: Incident) -> List["Evidence"]:
    """
    Fetch CI/CD evidence from GitHub Actions API.
    
    Requires settings:
    - GITHUB_TOKEN
    - GITHUB_OWNER
    - GITHUB_REPO
    - GITHUB_BRANCH (optional)
    - GITHUB_TIME_WINDOW_HOURS (optional)
    
    Returns:
        List of Evidence objects from GitHub Actions
        
    Raises:
        ValueError: If required GitHub configuration is missing
        RateLimitError: If GitHub API rate limit is exceeded
        GitHubAPIError: If GitHub API request fails
    """
    from backend.config import settings
    from backend.data_sources.github_actions import GitHubActionsClient, GitHubAPIError, RateLimitError
    from backend.data_sources.github_actions.adapter import normalize_to_agentops_cicd_schema
    from backend.models import Evidence, EvidenceType
    from datetime import datetime
    
    if not settings.github_token:
        raise ValueError("GITHUB_TOKEN is required but not configured. Please set GITHUB_TOKEN in environment.")
    
    if not settings.github_owner or not settings.github_repo:
        raise ValueError("GITHUB_OWNER and GITHUB_REPO are required but not configured. Please set GITHUB_OWNER and GITHUB_REPO in environment.")
    
    evidence = []
    try:
        async with GitHubActionsClient(token=settings.github_token) as client:
            incident_time = incident.detected_at if incident.detected_at else incident.started_at
            github_data = await client.fetch_cicd_data_for_incident(
                owner=settings.github_owner,
                repo=settings.github_repo,
                incident_time=incident_time,
                time_window_hours=settings.github_time_window_hours,
                branch=settings.github_branch,
            )
            
            cicd_data = normalize_to_agentops_cicd_schema(github_data)
            
            # Convert to Evidence objects
            for dep in cicd_data.deployments:
                evidence.append(Evidence(
                    investigation_id="",
                    agent_type="cicd_analyzer",
                    evidence_type=EvidenceType.DEPLOYMENT,
                    description=f"Deployment {dep.get('deployment_id', 'unknown')} at {dep.get('timestamp', 'unknown')}",
                    raw_data=dep,
                    confidence=0.8,
                    source="github_actions"
                ))
            
            for change in cicd_data.code_changes:
                evidence.append(Evidence(
                    investigation_id="",
                    agent_type="cicd_analyzer",
                    evidence_type=EvidenceType.CODE_CHANGE,
                    description=f"Code change in {change.get('file', 'unknown')}: {change.get('description', 'unknown')}",
                    raw_data=change,
                    confidence=0.7,
                    source="github_actions"
                ))
            
            for change in cicd_data.config_changes:
                evidence.append(Evidence(
                    investigation_id="",
                    agent_type="cicd_analyzer",
                    evidence_type=EvidenceType.CONFIG_CHANGE,
                    description=f"Config change: {change.get('key', 'unknown')} = {change.get('new_value', 'unknown')}",
                    raw_data=change,
                    confidence=0.85,
                    source="github_actions"
                ))
            
            for dep in cicd_data.dependency_changes:
                evidence.append(Evidence(
                    investigation_id="",
                    agent_type="cicd_analyzer",
                    evidence_type=EvidenceType.DEPENDENCY_CHANGE,
                    description=f"Dependency change: {dep.get('name', 'unknown')} {dep.get('old_version', '?')} -> {dep.get('new_version', '?')}",
                    raw_data=dep,
                    confidence=0.75,
                    source="github_actions"
                ))
            
            logger.info(f"Fetched {len(evidence)} CI/CD evidence items from GitHub Actions")
            
    except RateLimitError as e:
        logger.error(f"GitHub API rate limit exceeded: {e}")
        raise
    except GitHubAPIError as e:
        logger.error(f"GitHub API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching GitHub Actions data: {e}")
        raise
    
    return evidence


def get_cicd_evidence_from_fixture(incident: Incident) -> List["Evidence"]:
    """Load CI/CD evidence from local fixture files."""
    data = data_loader.load_cicd_data(incident.incident_id)
    evidence = []
    
    if data.get("deployments"):
        for dep in data["deployments"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type="cicd_analyzer",
                evidence_type=EvidenceType.DEPLOYMENT,
                description=f"Deployment {dep.get('deployment_id', 'unknown')} at {dep.get('timestamp', 'unknown')}",
                raw_data=dep,
                confidence=0.8,
                source="cicd_fixture"
            ))
    
    if data.get("code_changes"):
        for change in data["code_changes"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type="cicd_analyzer",
                evidence_type=EvidenceType.CODE_CHANGE,
                description=f"Code change in {change.get('file', 'unknown')}: {change.get('description', 'unknown')}",
                raw_data=change,
                confidence=0.7,
                source="cicd_fixture"
            ))
    
    if data.get("config_changes"):
        for change in data["config_changes"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type="cicd_analyzer",
                evidence_type=EvidenceType.CONFIG_CHANGE,
                description=f"Config change: {change.get('key', 'unknown')} = {change.get('new_value', 'unknown')}",
                raw_data=change,
                confidence=0.85,
                source="cicd_fixture"
            ))
    
    if data.get("dependency_changes"):
        for dep in data["dependency_changes"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type="cicd_analyzer",
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

    if data.get("pods"):
        for pod in data["pods"]:
            if "exit_code" in pod:
                evidence.append(Evidence(
                    investigation_id="",
                    agent_type="kubernetes_analyzer",
                    evidence_type=EvidenceType.POD_EXIT_CODE,
                    description=f"Pod {pod.get('name', 'unknown')} exited with code {pod['exit_code']}",
                    raw_data=pod,
                    confidence=0.9,
                    source="kubernetes_fixture"
                ))

            if "restart_count" in pod:
                evidence.append(Evidence(
                    investigation_id="",
                    agent_type="kubernetes_analyzer",
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
                        agent_type="kubernetes_analyzer",
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
                    agent_type="kubernetes_analyzer",
                    evidence_type=EvidenceType.RESOURCE_USAGE,
                    description=f"Pod {pod.get('name', 'unknown')} memory usage: {usage} / {limit}",
                    raw_data={"usage": usage, "limit": limit, "pod": pod.get('name')},
                    confidence=0.9,
                    source="kubernetes_fixture"
                ))
                evidence.append(Evidence(
                    investigation_id="",
                    agent_type="kubernetes_analyzer",
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

    if data.get("latency"):
        lat = data["latency"]
        evidence.append(Evidence(
            investigation_id="",
            agent_type="observability_analyzer",
            evidence_type=EvidenceType.LATENCY,
            description=f"P95 latency: {lat.get('p95', 'unknown')}, P99 latency: {lat.get('p99', 'unknown')}",
            raw_data=lat,
            confidence=0.85,
            source="observability_fixture"
        ))

    if data.get("error_rate"):
        err = data["error_rate"]
        evidence.append(Evidence(
            investigation_id="",
            agent_type="observability_analyzer",
            evidence_type=EvidenceType.ERROR_RATE,
            description=f"Error rate: {err.get('rate', 'unknown')}% ({err.get('count', 'unknown')} errors)",
            raw_data=err,
            confidence=0.9,
            source="observability_fixture"
        ))

    if data.get("logs"):
        for log in data["logs"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type="observability_analyzer",
                evidence_type=EvidenceType.LOG,
                description=f"Log: {log.get('message', 'unknown')}",
                raw_data=log,
                confidence=0.7,
                source="observability_fixture"
            ))

    if data.get("stack_traces"):
        for trace in data["stack_traces"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type="observability_analyzer",
                evidence_type=EvidenceType.STACK_TRACE,
                description=f"Stack trace: {trace.get('error', 'unknown')}",
                raw_data=trace,
                confidence=0.85,
                source="observability_fixture"
            ))

    if data.get("traces"):
        for trace in data["traces"]:
            evidence.append(Evidence(
                investigation_id="",
                agent_type="observability_analyzer",
                evidence_type=EvidenceType.TRACE,
                description=f"Trace {trace.get('trace_id', 'unknown')}: {trace.get('duration', 'unknown')}ms",
                raw_data=trace,
                confidence=0.8,
                source="observability_fixture"
            ))

    return evidence


def get_cicd_evidence(incident: Incident) -> List["Evidence"]:
    """
    Get CI/CD evidence, trying local fixtures first, then falling back to GitHub API.
    """
    # First try to load from local fixture
    fixture_evidence = get_cicd_evidence_from_fixture(incident)
    if fixture_evidence:
        return fixture_evidence
    
    # Fall back to GitHub API
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(get_cicd_evidence_from_github(incident))
    except Exception as e:
        logger.warning(f"GitHub API fetch failed, returning empty evidence: {e}")
        return []