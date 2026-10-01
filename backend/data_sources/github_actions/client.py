import os
import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .models import (
    WorkflowRun,
    WorkflowJob,
    WorkflowJobLog,
    Commit,
    DeploymentStatus,
    Repository,
    GitHubEventData,
    GitHubActionsCICDData,
    WorkflowRunStatus,
    WorkflowRunConclusion,
)

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    def __init__(self, message: str, status_code: int = None, response: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class RateLimitError(GitHubAPIError):
    def __init__(self, message: str = "Rate limit exceeded", reset_at: datetime = None):
        super().__init__(message, status_code=403)
        self.reset_at = reset_at


class GitHubActionsClient:
    BASE_URL = "https://api.github.com"
    
    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable or pass token parameter.")
        
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "AgentOps-CICD-Adapter/1.0",
            },
            timeout=timeout,
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        await self.client.aclose()
    
    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        if response.status_code == 403:
            reset_header = response.headers.get("X-RateLimit-Reset")
            reset_at = None
            if reset_header:
                reset_at = datetime.fromtimestamp(int(reset_header))
            raise RateLimitError("GitHub API rate limit exceeded", reset_at=reset_at)
        
        if response.status_code == 401:
            raise GitHubAPIError("Invalid GitHub token", status_code=401)
        
        if response.status_code == 404:
            raise GitHubAPIError("Resource not found", status_code=404)
        
        if response.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub API error: {response.status_code}",
                status_code=response.status_code,
                response=response.text
            )
        
        return response.json()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, RateLimitError)),
    )
    async def _request(self, method: str, path: str, params: Dict = None, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = await self.client.request(method, url, params=params, **kwargs)
        return self._handle_response(response)
    
    async def get_workflow_runs(
        self,
        owner: str,
        repo: str,
        branch: Optional[str] = None,
        event: Optional[str] = None,
        status: Optional[WorkflowRunStatus] = None,
        conclusion: Optional[WorkflowRunConclusion] = None,
        per_page: int = 30,
        page: int = 1,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ) -> List[WorkflowRun]:
        params = {
            "per_page": per_page,
            "page": page,
        }
        if branch:
            params["branch"] = branch
        if event:
            params["event"] = event
        if status:
            params["status"] = status.value if hasattr(status, 'value') else status
        if conclusion:
            params["conclusion"] = conclusion.value if hasattr(conclusion, 'value') else conclusion
        if created_after:
            params["created"] = f">{created_after.isoformat()}"
        if created_before:
            params["created"] = f"<{created_before.isoformat()}"
        
        data = await self._request("GET", f"/repos/{owner}/{repo}/actions/runs", params=params)
        runs = data.get("workflow_runs", [])
        runs = [WorkflowRun(**run) for run in runs]
        
        # Client-side filtering for conclusion since GitHub API may not filter correctly
        if conclusion:
            conclusion_value = conclusion.value if hasattr(conclusion, 'value') else conclusion
            runs = [run for run in runs if run.conclusion == conclusion_value]
        
        return runs
    
    async def get_workflow_jobs(
        self,
        owner: str,
        repo: str,
        run_id: int,
        per_page: int = 100,
    ) -> List[WorkflowJob]:
        params = {"per_page": per_page}
        data = await self._request("GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs", params=params)
        jobs = data.get("jobs", [])
        return [WorkflowJob(**job) for job in jobs]
    
    async def get_job_logs(
        self,
        owner: str,
        repo: str,
        job_id: int,
    ) -> str:
        # GitHub Actions job logs endpoint returns a redirect to the actual logs URL
        # We need to follow redirects and accept the appropriate content type
        response = await self.client.get(
            f"/repos/{owner}/{repo}/actions/jobs/{job_id}/logs",
            headers={"Accept": "application/vnd.github+json"},
            follow_redirects=True,
        )
        if response.status_code == 403:
            raise RateLimitError("Rate limit exceeded")
        if response.status_code == 404:
            raise GitHubAPIError("Job logs not found", status_code=404)
        if response.status_code == 302 or response.status_code == 301:
            # Follow redirect to get actual logs
            redirect_url = response.headers.get("Location")
            if redirect_url:
                logs_response = await self.client.get(redirect_url, follow_redirects=True)
                if logs_response.status_code == 200:
                    return logs_response.text
        return response.text
    
    async def get_commits(
        self,
        owner: str,
        repo: str,
        sha: str,
        per_page: int = 100,
    ) -> List[Commit]:
        params = {"per_page": per_page}
        data = await self._request("GET", f"/repos/{owner}/{repo}/commits/{sha}", params=params)
        return Commit(**data)
    
    async def get_commits_between(
        self,
        owner: str,
        repo: str,
        base: str,
        head: str,
        per_page: int = 100,
    ) -> List[Commit]:
        params = {"per_page": per_page}
        data = await self._request("GET", f"/repos/{owner}/{repo}/compare/{base}...{head}", params=params)
        commits = data.get("commits", [])
        return [Commit(**commit) for commit in commits]
    
    async def get_deployments(
        self,
        owner: str,
        repo: str,
        environment: Optional[str] = None,
        per_page: int = 30,
    ) -> List[DeploymentStatus]:
        params = {"per_page": per_page}
        if environment:
            params["environment"] = environment
        data = await self._request("GET", f"/repos/{owner}/{repo}/deployments", params=params)
        deployments = []
        for dep in data:
            statuses = await self.get_deployment_statuses(owner, repo, dep["id"])
            dep["statuses"] = statuses
            deployments.append(DeploymentStatus(**dep))
        return deployments
    
    async def get_deployment_statuses(
        self,
        owner: str,
        repo: str,
        deployment_id: int,
    ) -> List[DeploymentStatus]:
        data = await self._request("GET", f"/repos/{owner}/{repo}/deployments/{deployment_id}/statuses")
        return [DeploymentStatus(**status) for status in data]
    
    async def get_repository_events(
        self,
        owner: str,
        repo: str,
        per_page: int = 30,
    ) -> List[GitHubEventData]:
        data = await self._request("GET", f"/repos/{owner}/{repo}/events", params={"per_page": per_page})
        events = []
        for event in data:
            events.append(GitHubEventData(**event))
        return events
    
    async def get_repository(self, owner: str, repo: str) -> Repository:
        data = await self._request("GET", f"/repos/{owner}/{repo}")
        return Repository(**data)
    
    async def get_workflow_run(self, owner: str, repo: str, run_id: int) -> WorkflowRun:
        data = await self._request("GET", f"/repos/{owner}/{repo}/actions/runs/{run_id}")
        return WorkflowRun(**data)
    
    async def fetch_cicd_data_for_incident(
        self,
        owner: str,
        repo: str,
        incident_time: datetime,
        time_window_hours: int = 24,
        branch: Optional[str] = None,
    ) -> GitHubActionsCICDData:
        """
        Fetch all relevant CI/CD data for a specific incident time window.
        
        Args:
            owner: Repository owner
            repo: Repository name
            incident_time: When the incident occurred
            time_window_hours: How far back to look for relevant CI/CD activity
            branch: Specific branch to filter (optional)
        
        Returns:
            GitHubActionsCICDData with all relevant CI/CD data
        """
        start_time = incident_time - timedelta(hours=time_window_hours)
        end_time = incident_time + timedelta(hours=1)
        
        workflow_runs = await self.get_workflow_runs(
            owner=owner,
            repo=repo,
            branch=branch,
            status=WorkflowRunStatus.COMPLETED,
            created_after=start_time,
            created_before=end_time,
            per_page=100,
        )
        
        all_jobs = []
        for run in workflow_runs:
            jobs = await self.get_workflow_jobs(owner, repo, run.id)
            all_jobs.extend(jobs)
        
        deployments = await self.get_deployments(owner, repo)
        
        commits = []
        for run in workflow_runs:
            try:
                commit = await self.get_commits(owner, repo, run.head_sha)
                commits.append(commit)
            except GitHubAPIError:
                pass
        
        repo_info = await self.get_repository(owner, repo)
        
        return GitHubActionsCICDData(
            workflow_runs=workflow_runs,
            workflow_jobs=all_jobs,
            commits=commits,
            deployments=deployments,
            repository=repo_info,
        )