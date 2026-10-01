import logging
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timedelta
from collections import defaultdict

from .models import (
    GitHubActionsCICDData,
    AgentOpsCICDData,
    WorkflowRun,
    WorkflowJob,
    Commit,
    DeploymentStatus,
    WorkflowRunConclusion,
    JobConclusion,
)
from backend.models import EvidenceType, AgentType

logger = logging.getLogger(__name__)


class GitHubActionsAdapter:
    """
    Adapter to transform GitHub Actions API data into AgentOps CI/CD schema.
    
    This adapter converts raw GitHub Actions API responses into the existing
    AgentOps CI/CD JSON schema so that the rest of the system continues working
    without modification.
    
    Key transformations:
    - Workflow runs → deployments
    - Commit file changes → code_changes
    - Workflow configuration → config_changes
    - Dependency updates from dependabot → dependency_changes
    - Workflow strategy → rollout_info
    
    Fields that CANNOT be obtained from GitHub Actions API and will be left empty:
    - Kubernetes namespace (not available in GitHub Actions)
    - Replica count (not available)
    - Container image version (only available if explicitly in workflow)
    - Rollout strategy details (max_surge, max_unavailable, canary_percentage)
    - Kubernetes-specific config changes (resources.limits.memory, etc.)
    """
    
    def __init__(self, include_raw_data: bool = False):
        self.include_raw_data = include_raw_data
    
    def adapt(self, github_data: GitHubActionsCICDData) -> AgentOpsCICDData:
        """
        Transform GitHub Actions data into AgentOps CI/CD schema.
        
        Args:
            github_data: Raw GitHub Actions data from API
            
        Returns:
            AgentOpsCICDData compatible with existing CI/CD schema
        """
        deployments = self._extract_deployments(github_data)
        code_changes = self._extract_code_changes(github_data)
        config_changes = self._extract_config_changes(github_data)
        dependency_changes = self._extract_dependency_changes(github_data)
        rollout_info = self._extract_rollout_info(github_data)
        
        return AgentOpsCICDData(
            deployments=deployments,
            code_changes=code_changes,
            config_changes=config_changes,
            dependency_changes=dependency_changes,
            rollout_info=rollout_info,
            source="github_actions",
            raw_data=github_data.model_dump() if self.include_raw_data else None,
        )
    
    def _extract_deployments(self, github_data: GitHubActionsCICDData) -> List[Dict[str, Any]]:
        """
        Extract deployment information from workflow runs and deployment statuses.
        
        From GitHub Actions:
        - Workflow runs with deployment-related jobs
        - Deployment status objects
        
        Fields available:
        - deployment_id (run_id)
        - timestamp (run_started_at / created_at)
        - service (repository name)
        - namespace: NOT AVAILABLE (leave empty)
        - image: NOT DIRECTLY AVAILABLE (workflow may build/push but not standardized)
        - previous_image: NOT AVAILABLE
        - strategy: from workflow or deployment (partial)
        - replicas: NOT AVAILABLE
        - status: from conclusion
        
        Returns:
            List of deployment dicts compatible with AgentOps schema
        """
        deployments = []
        
        # From workflow runs
        for run in github_data.workflow_runs:
            if run.conclusion in [WorkflowRunConclusion.SUCCESS, WorkflowRunConclusion.FAILURE]:
                # Check if this looks like a deployment workflow
                is_deployment = self._is_deployment_workflow(run)
                
                if is_deployment or self._has_deployment_jobs(github_data.workflow_jobs, run.id):
                    dep = {
                        "deployment_id": f"gh-{run.id}",
                        "timestamp": run.run_started_at.isoformat() if run.run_started_at else run.created_at.isoformat(),
                        "service": github_data.repository.name if github_data.repository else "unknown",
                        "namespace": None,  # NOT AVAILABLE from GitHub Actions
                        "image": self._extract_image_from_workflow(run, github_data.workflow_jobs),
                        "previous_image": None,  # NOT AVAILABLE
                        "strategy": self._extract_strategy(run),
                        "replicas": None,  # NOT AVAILABLE
                        "status": run.conclusion.value if run.conclusion else "unknown",
                        "workflow_name": run.name,
                        "workflow_run_id": run.id,
                        "commit_sha": run.head_sha,
                        "branch": run.head_branch,
                        "source": "github_actions_workflow",
                    }
                    deployments.append(dep)
        
        # From GitHub Deployments API
        for deployment in github_data.deployments:
            if deployment.statuses:
                latest_status = max(deployment.statuses, key=lambda s: s.created_at)
                dep = {
                    "deployment_id": f"gh-deploy-{deployment.id}",
                    "timestamp": latest_status.created_at.isoformat(),
                    "service": github_data.repository.name if github_data.repository else "unknown",
                    "namespace": None,  # NOT AVAILABLE
                    "image": self._extract_image_from_deployment(deployment),
                    "previous_image": None,
                    "strategy": None,
                    "replicas": None,
                    "status": latest_status.state,
                    "environment": deployment.environment,
                    "deployment_id": deployment.id,
                    "commit_sha": deployment.deployment.get("sha") if isinstance(deployment.deployment, dict) else None,
                    "source": "github_actions_deployment",
                }
                deployments.append(dep)
        
        return deployments
    
    def _extract_code_changes(self, github_data: GitHubActionsCICDData) -> List[Dict[str, Any]]:
        """
        Extract code changes from commits in workflow runs.
        
        From GitHub Actions:
        - Commits associated with workflow runs
        - Can use compare API to get file changes
        
        Fields available:
        - file: from commit files (via compare API)
        - description: commit message or file change summary
        - author: commit author
        - commit: commit SHA
        - timestamp: commit timestamp
        
        Fields NOT available without additional API calls:
        - Full diff (requires separate API call per commit)
        - Line-by-line changes
        """
        code_changes = []
        seen_files: Set[str] = set()
        
        for commit in github_data.commits:
            commit_data = commit.model_dump() if hasattr(commit, 'model_dump') else commit
            if isinstance(commit, Commit):
                files = self._get_files_from_commit(commit)
                for file in files:
                    if file not in seen_files:
                        seen_files.add(file)
                        code_changes.append({
                            "file": file,
                            "description": commit.message.split('\n')[0] if commit.message else "Code change",
                            "author": commit.author.get("name") if commit.author else "unknown",
                            "commit": commit.sha[:8],
                            "timestamp": commit.author.get("date") if commit.author else None,
                            "commit_sha": commit.sha,
                            "source": "github_actions_commit",
                        })
        
        return code_changes
    
    def _extract_config_changes(self, github_data: GitHubActionsCICDData) -> List[Dict[str, Any]]:
        """
        Extract configuration changes from workflow files and repository settings.
        
        From GitHub Actions:
        - Workflow YAML changes (detected via commit file paths)
        - Repository settings changes (not directly available)
        
        Fields available:
        - key: configuration key (e.g., "workflow.env.VAR", "workflow.job.env")
        - old_value: NOT DIRECTLY AVAILABLE
        - new_value: current value from workflow
        - timestamp: commit timestamp
        - changed_by: commit author
        
        LIMITATIONS:
        - Cannot get old values without fetching previous workflow version
        - Kubernetes-specific configs (resources.limits.memory) NOT AVAILABLE
        - Environment variables from workflow are available
        """
        config_changes = []
        
        for commit in github_data.commits:
            if isinstance(commit, Commit):
                # Check if commit modified workflow files
                workflow_files = self._get_workflow_files_from_commit(commit)
                for wf_file in workflow_files:
                    config_changes.append({
                        "key": f"workflow.{wf_file}",
                        "old_value": None,  # NOT AVAILABLE without previous version
                        "new_value": "workflow modified",  # Would need to parse YAML
                        "timestamp": commit.author.get("date") if commit.author else None,
                        "changed_by": commit.author.get("name") if commit.author else "unknown",
                        "commit_sha": commit.sha[:8],
                        "source": "github_actions_workflow_change",
                    })
        
        # Extract environment variables from workflow runs
        for run in github_data.workflow_runs:
            # This would require parsing workflow YAML which is not in API response
            pass
        
        return config_changes
    
    def _extract_dependency_changes(self, github_data: GitHubActionsCICDData) -> List[Dict[str, Any]]:
        """
        Extract dependency changes from dependabot or commit changes.
        
        From GitHub Actions:
        - Dependabot PRs (workflow runs triggered by dependabot)
        - Package lock file changes in commits
        
        Fields available:
        - name: package name (from dependabot title or lock file)
        - old_version: NOT DIRECTLY AVAILABLE
        - new_version: NOT DIRECTLY AVAILABLE
        - timestamp: PR creation or commit time
        
        LIMITATIONS:
        - Version extraction requires parsing lock files or PR titles
        - Not all dependency updates go through GitHub Actions
        """
        dependency_changes = []
        
        for run in github_data.workflow_runs:
            # Check if triggered by dependabot
            if run.actor and run.actor.get("login", "").lower() in ["dependabot", "dependabot[bot]"]:
                # Extract package info from workflow run
                dep_name = self._extract_dependabot_package(run)
                if dep_name:
                    dependency_changes.append({
                        "name": dep_name,
                        "old_version": None,  # NOT AVAILABLE
                        "new_version": None,  # NOT AVAILABLE
                        "timestamp": run.created_at.isoformat(),
                        "workflow_run_id": run.id,
                        "source": "github_actions_dependabot",
                    })
        
        return dependency_changes
    
    def _extract_rollout_info(self, github_data: GitHubActionsCICDData) -> Dict[str, Any]:
        """
        Extract rollout strategy information from workflow configuration.
        
        LIMITATIONS:
        - Kubernetes-specific rollout info NOT AVAILABLE
        - Can only extract GitHub Actions workflow strategy
        """
        rollout_info = {
            "type": "github_actions_workflow",
            "max_surge": None,  # NOT AVAILABLE (K8s concept)
            "max_unavailable": None,  # NOT AVAILABLE (K8s concept)
            "canary_percentage": None,  # NOT AVAILABLE
        }
        
        # Try to extract from workflow configuration
        # This would require parsing workflow YAML which is not in the API response
        
        return rollout_info
    
    def _is_deployment_workflow(self, run: WorkflowRun) -> bool:
        """Check if a workflow run is deployment-related."""
        deployment_keywords = [
            "deploy", "release", "publish", "delivery", "promote",
            "staging", "production", "prod", "stage"
        ]
        run_name = run.name.lower() if run.name else ""
        return any(keyword in run_name for keyword in deployment_keywords)
    
    def _has_deployment_jobs(self, jobs: List[WorkflowJob], run_id: int) -> bool:
        """Check if a workflow run has deployment-related jobs."""
        run_jobs = [j for j in jobs if j.run_id == run_id]
        deployment_keywords = ["deploy", "release", "publish", "delivery"]
        for job in run_jobs:
            if any(keyword in job.name.lower() for keyword in deployment_keywords):
                return True
        return False
    
    def _extract_image_from_workflow(self, run: WorkflowRun, jobs: List[WorkflowJob]) -> Optional[str]:
        """Extract container image from workflow - NOT DIRECTLY AVAILABLE."""
        # Would require parsing workflow YAML or job steps
        return None
    
    def _extract_image_from_deployment(self, deployment: DeploymentStatus) -> Optional[str]:
        """Extract container image from deployment - NOT DIRECTLY AVAILABLE."""
        # Deployment payload might have image info but not standardized
        return None
    
    def _extract_strategy(self, run: WorkflowRun) -> Optional[str]:
        """Extract deployment strategy - NOT DIRECTLY AVAILABLE."""
        return "github_actions"
    
    def _get_files_from_commit(self, commit: Commit) -> List[str]:
        """Get list of files changed in a commit. Requires additional API call."""
        # This would require a separate API call to get commit files
        # For now, return empty - would need /repos/{owner}/{repo}/commits/{sha}
        return []
    
    def _get_workflow_files_from_commit(self, commit: Commit) -> List[str]:
        """Get workflow files (.github/workflows/*.yml) changed in commit."""
        return []
    
    def _extract_dependabot_package(self, run: WorkflowRun) -> Optional[str]:
        """Extract package name from dependabot workflow run title."""
        if run.name and "dependabot" in run.name.lower():
            # Try to extract package name from title like "Bump actions/checkout from 3 to 4"
            import re
            match = re.search(r'bump\s+([\w\-\./]+)', run.name.lower())
            if match:
                return match.group(1)
            match = re.search(r'update\s+([\w\-\./]+)', run.name.lower())
            if match:
                return match.group(1)
        return None
    
    def _parse_workflow_for_env_vars(self, workflow_yaml: str) -> Dict[str, str]:
        """Parse workflow YAML for environment variables."""
        return {}


def normalize_to_agentops_cicd_schema(github_data: GitHubActionsCICDData) -> AgentOpsCICDData:
    """
    Convenience function to normalize GitHub Actions data to AgentOps CI/CD schema.
    
    Args:
        github_data: Raw GitHub Actions data from API
        
    Returns:
        AgentOpsCICDData compatible with existing CI/CD schema
    """
    adapter = GitHubActionsAdapter()
    return adapter.adapt(github_data)