import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from backend.config import settings
from backend.data_sources.github_actions import GitHubActionsClient, GitHubAPIError, RateLimitError
from backend.data_sources.github_actions.models import (
    WorkflowRun, WorkflowJob, Commit, DeploymentStatus,
    WorkflowRunStatus, WorkflowRunConclusion, JobStatus, JobConclusion
)
from backend.data_sources.github_actions.adapter import normalize_to_agentops_cicd_schema
from backend.models import (
    Incident, IncidentSeverity, IncidentStatus,
    Evidence, AgentType, EvidenceType
)
from backend.services.investigation_service import investigation_service
from backend.services.mongodb import mongodb
from backend.models.mongodb import IncidentDoc, ProcessedRunDoc

logger = logging.getLogger(__name__)


class ProcessedRunTracker:
    """Track processed GitHub workflow run IDs using MongoDB for persistence."""
    
    def __init__(self):
        self._processed_runs: set[int] = set()
        self._loaded = False
    
    async def load(self):
        """Load processed run IDs from MongoDB."""
        if self._loaded:
            return
        try:
            docs = await ProcessedRunDoc.find_all().to_list()
            self._processed_runs = {doc.run_id for doc in docs}
            self._loaded = True
            logger.info(f"Loaded {len(self._processed_runs)} previously processed workflow runs")
        except Exception as e:
            logger.warning(f"Could not load processed runs from MongoDB: {e}")
            self._loaded = True
    
    def is_processed(self, run_id: int) -> bool:
        return run_id in self._processed_runs
    
    async def mark_processed(self, run_id: int, workflow_name: str, run_number: int, concluded_at: datetime):
        self._processed_runs.add(run_id)
        try:
            doc = ProcessedRunDoc(
                run_id=run_id,
                workflow_name=workflow_name,
                run_number=run_number,
                concluded_at=concluded_at
            )
            await doc.insert()
        except Exception as e:
            logger.warning(f"Could not persist processed run {run_id}: {e}")


class GitHubActionsMonitor:
    """
    Monitors GitHub Actions for failed workflow runs and automatically creates AgentOps incidents.
    """
    
    def __init__(
        self,
        owner: str,
        repo: str,
        branch: Optional[str] = None,
        poll_interval_seconds: int = 60,
        time_window_hours: int = 24,
    ):
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self.poll_interval_seconds = poll_interval_seconds
        self.time_window_hours = time_window_hours
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self.processed_runs = ProcessedRunTracker()
        self._client: Optional[GitHubActionsClient] = None
    
    async def start(self):
        """Start the monitoring process."""
        if self._running:
            logger.warning("Monitor already running")
            return
        
        # Initialize GitHub client
        if not settings.github_token:
            raise ValueError("GITHUB_TOKEN is required but not configured")
        
        self._client = GitHubActionsClient(token=settings.github_token)
        await self.processed_runs.load()
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(
            f"GitHub Actions monitor started for {self.owner}/{self.repo} "
            f"(branch={self.branch}, poll_interval={self.poll_interval_seconds}s, time_window={self.time_window_hours}h)"
        )
    
    async def stop(self):
        """Stop the monitoring process."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._client:
            await self._client.close()
        logger.info("GitHub Actions monitor stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info("GitHub Actions monitor loop started")
        
        while self._running:
            try:
                await self._check_for_failed_runs()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
            
            # Wait for next poll interval
            try:
                await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                break
        
        logger.info("GitHub Actions monitor loop stopped")
    
    async def _check_for_failed_runs(self):
        """Check for new failed workflow runs and process them."""
        if not self._client:
            logger.warning("GitHub client not initialized, skipping check")
            return
        
        try:
            logger.debug(f"Checking for failed workflow runs in {self.owner}/{self.repo}")
            
            # Calculate time window
            end_time = datetime.utcnow()
            start_time = datetime.utcnow() - timedelta(hours=self.time_window_hours)
            
            # Fetch recent workflow runs
            runs = await self._client.get_workflow_runs(
                owner=self.owner,
                repo=self.repo,
                branch=self.branch,
                status=WorkflowRunStatus.COMPLETED,
                conclusion=WorkflowRunConclusion.FAILURE,
                created_after=start_time,
                created_before=end_time,
                per_page=50,
            )
            
            logger.info(f"Found {len(runs)} completed failed workflow runs in time window")
            
            # Filter for new failures
            new_failures = []
            for run in runs:
                if not self.processed_runs.is_processed(run.id):
                    new_failures.append(run)
            
            if not new_failures:
                logger.debug("No new failed workflow runs to process")
                return
            
            logger.info(f"Found {len(new_failures)} new failed workflow runs to process")
            
            # Process each new failure
            for run in new_failures:
                try:
                    await self._process_failed_run(run)
                except Exception as e:
                    logger.error(f"Failed to process run {run.id}: {e}", exc_info=True)
                    # Continue processing other runs
            
        except RateLimitError as e:
            logger.warning(f"GitHub API rate limit hit, will retry next cycle: {e}")
        except GitHubAPIError as e:
            logger.error(f"GitHub API error during polling: {e}")
        except Exception as e:
            logger.error(f"Unexpected error checking for failed runs: {e}", exc_info=True)
    
    async def _process_failed_run(self, run: WorkflowRun):
        """Process a single failed workflow run: create incident, fetch evidence, start investigation."""
        logger.info(f"Processing failed workflow run: {run.id} ({run.name})")
        
        try:
            # Fetch detailed data for this run
            jobs = await self._client.get_workflow_jobs(self.owner, self.repo, run.id)
            
            # Fetch commit information
            commit = None
            try:
                commit = await self._client.get_commits(self.owner, self.repo, run.head_sha)
            except Exception as e:
                logger.warning(f"Could not fetch commit {run.head_sha}: {e}")
            
            # Fetch job logs for failed jobs
            job_logs = {}
            failed_jobs = [j for j in jobs if j.conclusion == JobConclusion.FAILURE]
            for job in failed_jobs[:3]:  # Limit to first 3 failed jobs to avoid excessive API calls
                try:
                    logs = await self._client.get_job_logs(self.owner, self.repo, job.id)
                    job_logs[job.id] = logs
                except Exception as e:
                    logger.warning(f"Could not fetch logs for job {job.id}: {e}")
            
            # Create or get existing incident
            incident = await self._create_incident(run)
            
            # Mark run as processed early to prevent duplicate processing
            concluded_at = run.updated_at if run.updated_at else run.created_at
            await self.processed_runs.mark_processed(run.id, run.name, run.run_number, concluded_at)
            
            # Fetch CI/CD evidence from GitHub Actions
            logger.info(f"Fetching CI/CD evidence for incident {incident.incident_id}")
            github_evidence = await self._fetch_github_evidence_for_run(run, jobs, job_logs)
            
            # Start investigation with the fetched evidence
            logger.info(f"Starting investigation for incident {incident.incident_id}")
            from backend.services.investigation_service import investigation_service
            result = await investigation_service.start_investigation(incident, max_iterations=2, evidence=github_evidence)
            
            logger.info(
                f"Successfully processed failed run {run.id}: "
                f"incident={incident.incident_id}, investigation={result.investigation_id}"
            )
            
        except Exception as e:
            logger.error(f"Error processing failed run {run.id}: {e}", exc_info=True)
            raise
    
    async def _create_incident(self, run: WorkflowRun) -> Incident:
        """Create an AgentOps incident from a failed workflow run."""
        # Determine severity based on workflow characteristics
        severity = IncidentSeverity.HIGH
        if "production" in run.name.lower() or "prod" in run.name.lower():
            severity = IncidentSeverity.CRITICAL
        elif "staging" in run.name.lower() or "stage" in run.name.lower():
            severity = IncidentSeverity.HIGH
        else:
            severity = IncidentSeverity.MEDIUM
        
        # Use workflow run completion time or current time
        completed_at = run.updated_at if run.updated_at else run.created_at
        
        incident = Incident(
            incident_id=f"github-actions-{run.id}",
            title=f"GitHub Actions workflow failed: {run.name}",
            description=(
                f"Workflow '{run.name}' failed on branch {run.head_branch} "
                f"for commit {run.head_sha[:8]}. "
                f"Run number: {run.run_number}, URL: {run.html_url}"
            ),
            severity=severity,
            status=IncidentStatus.OPEN,
            source="github_actions",
            service_name=self.repo,
            namespace="github-actions",
            started_at=run.created_at,
            detected_at=run.updated_at if run.updated_at else run.created_at,
            metadata={
                "github_workflow_run_id": run.id,
                "github_workflow_name": run.name,
                "github_workflow_run_number": run.run_number,
                "github_repository": f"{self.owner}/{self.repo}",
                "github_branch": run.head_branch,
                "github_commit_sha": run.head_sha,
                "github_workflow_url": run.html_url,
            },
            tags=["github_actions", "automated", run.name.lower().replace(" ", "_")],
        )
        
        # Save incident to MongoDB - check if already exists first
        existing_incident = await IncidentDoc.find_one({"incident_id": incident.incident_id})
        if existing_incident:
            logger.info(f"Incident {incident.incident_id} already exists, using existing")
            incident = Incident(
                incident_id=existing_incident.incident_id,
                title=existing_incident.title,
                description=existing_incident.description,
                severity=existing_incident.severity,
                status=existing_incident.status,
                source=existing_incident.source,
                service_name=existing_incident.service_name,
                namespace=existing_incident.namespace,
                started_at=existing_incident.started_at,
                detected_at=existing_incident.detected_at,
                metadata=existing_incident.metadata,
                tags=existing_incident.tags,
            )
        else:
            incident_doc = IncidentDoc(
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
            await incident_doc.insert()
        
        return incident
    
    async def _fetch_github_evidence_for_run(
        self, 
        run: WorkflowRun, 
        jobs: List[WorkflowJob],
        job_logs: dict[int, str]
    ) -> List["Evidence"]:
        """Fetch comprehensive evidence from GitHub Actions for a specific workflow run."""
        from backend.data_sources.github_actions import GitHubActionsClient
        from backend.data_sources.github_actions.adapter import normalize_to_agentops_cicd_schema
        from backend.models import Evidence, AgentType, EvidenceType
        from backend.data_sources.github_actions.models import GitHubActionsCICDData
        
        evidence = []
        
        try:
            async with GitHubActionsClient(token=settings.github_token) as client:
                incident_time = run.updated_at if run.updated_at else run.created_at
                
                # Use the existing client methods to fetch data for this specific run
                jobs_data = await client.get_workflow_jobs(self.owner, self.repo, run.id)
                
                commit = None
                try:
                    commit = await client.get_commits(self.owner, self.repo, run.head_sha)
                except Exception:
                    pass
                
                deployments = await client.get_deployments(self.owner, self.repo)
                repo_info = await client.get_repository(self.owner, self.repo)
                
                # Create GitHubActionsCICDData for this run
                github_data = GitHubActionsCICDData(
                    workflow_runs=[run],
                    workflow_jobs=jobs_data,
                    commits=[commit] if commit else [],
                    deployments=[],
                    repository=repo_info,
                )
                
                # Normalize to AgentOps schema
                cicd_data = normalize_to_agentops_cicd_schema(github_data)
                
                # Convert to Evidence objects
                from backend.models import Evidence, AgentType, EvidenceType
                
                for dep in cicd_data.deployments:
                    evidence.append(Evidence(
                        investigation_id="",
                        agent_type=AgentType.CICD,
                        evidence_type=EvidenceType.DEPLOYMENT,
                        description=f"Deployment {dep.get('deployment_id', 'unknown')} at {dep.get('timestamp', 'unknown')}",
                        raw_data=dep,
                        confidence=0.8,
                        source="github_actions"
                    ))
                
                for change in cicd_data.code_changes:
                    evidence.append(Evidence(
                        investigation_id="",
                        agent_type=AgentType.CICD,
                        evidence_type=EvidenceType.CODE_CHANGE,
                        description=f"Code change in {change.get('file', 'unknown')}: {change.get('description', 'unknown')}",
                        raw_data=change,
                        confidence=0.7,
                        source="github_actions"
                    ))
                
                for change in cicd_data.config_changes:
                    evidence.append(Evidence(
                        investigation_id="",
                        agent_type=AgentType.CICD,
                        evidence_type=EvidenceType.CONFIG_CHANGE,
                        description=f"Config change: {change.get('key', 'unknown')} = {change.get('new_value', 'unknown')}",
                        raw_data=change,
                        confidence=0.85,
                        source="github_actions"
                    ))
                
                for dep in cicd_data.dependency_changes:
                    evidence.append(Evidence(
                        investigation_id="",
                        agent_type=AgentType.CICD,
                        evidence_type=EvidenceType.DEPENDENCY_CHANGE,
                        description=f"Dependency change: {dep.get('name', 'unknown')} {dep.get('old_version', '?')} -> {dep.get('new_version', '?')}",
                        raw_data=dep,
                        confidence=0.75,
                        source="github_actions"
                    ))
                
                # Add job-specific evidence
                for job in jobs_data:
                    if job.conclusion == JobConclusion.FAILURE:
                        evidence.append(Evidence(
                            investigation_id="",
                            agent_type=AgentType.CICD,
                            evidence_type=EvidenceType.JOB_FAILURE,
                            description=f"Job '{job.name}' failed: {job.conclusion}",
                            raw_data={
                                "job_id": job.id,
                                "job_name": job.name,
                                "status": job.status,
                                "conclusion": job.conclusion,
                                "started_at": job.started_at.isoformat() if job.started_at else None,
                                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                                "steps": job.steps,
                            },
                            confidence=0.9,
                            source="github_actions_job_logs"
                        ))
                        
                        # Add job logs if available
                        if job.id in job_logs:
                            logs = job_logs[job.id]
                            evidence.append(Evidence(
                                investigation_id="",
                                agent_type=AgentType.CICD,
                                evidence_type=EvidenceType.LOG,
                                description=f"Logs for failed job '{job.name}'",
                                raw_data={"logs": logs[:10000]},  # Truncate to 10KB
                                confidence=0.95,
                                source="github_actions_job_logs"
                            ))
                
                logger.info(f"Fetched {len(evidence)} CI/CD evidence items from GitHub Actions for run {run.id}")
                
        except Exception as e:
            logger.error(f"Error fetching GitHub evidence for run {run.id}: {e}")
        
        return evidence


# Global monitor instance
_github_monitor: Optional["GitHubActionsMonitor"] = None


async def start_github_monitor():
    """Start the GitHub Actions monitor as a background task."""
    global _github_monitor
    
    if _github_monitor is not None:
        logger.warning("GitHub monitor already running")
        return
    
    # Get configuration from settings
    owner = settings.github_owner
    repo = settings.github_repo
    branch = settings.github_branch
    poll_interval = getattr(settings, 'github_poll_interval_seconds', 60)
    time_window = getattr(settings, 'github_time_window_hours', 24)
    
    if not all([settings.github_token, owner, repo]):
        logger.warning("GitHub Actions monitor not started: missing required configuration (GITHUB_TOKEN, GITHUB_OWNER, GITHUB_REPO)")
        return
    
    monitor = GitHubActionsMonitor(
        owner=owner,
        repo=repo,
        branch=branch,
        poll_interval_seconds=poll_interval,
        time_window_hours=time_window,
    )
    
    _github_monitor = monitor
    await monitor.start()
    logger.info("GitHub Actions monitor started successfully")


async def stop_github_monitor():
    """Stop the GitHub Actions monitor."""
    global _github_monitor
    
    if _github_monitor is not None:
        await _github_monitor.stop()
        _github_monitor = None
        logger.info("GitHub Actions monitor stopped")


# Export for use in main.py lifespan
__all__ = ["GitHubActionsMonitor", "start_github_monitor", "stop_github_monitor"]