import pytest
from datetime import datetime
from backend.data_sources.github_actions.models import (
    WorkflowRun,
    WorkflowJob,
    Commit,
    DeploymentStatus,
    Repository,
    GitHubActionsCICDData,
    AgentOpsCICDData,
    WorkflowRunStatus,
    WorkflowRunConclusion,
    JobStatus,
    JobConclusion,
)


class TestGitHubActionsModels:
    """Test GitHub Actions data models."""
    
    def test_workflow_run_model(self):
        """Test WorkflowRun model creation and validation."""
        data = {
            "id": 12345,
            "name": "Deploy to Production",
            "head_branch": "main",
            "head_sha": "abc123def456",
            "run_number": 42,
            "event": "push",
            "status": "completed",
            "conclusion": "success",
            "workflow_id": 67890,
            "url": "https://api.github.com/repos/owner/repo/actions/runs/12345",
            "html_url": "https://github.com/owner/repo/actions/runs/12345",
            "created_at": "2024-01-15T10:28:00Z",
            "updated_at": "2024-01-15T10:35:00Z",
            "run_started_at": "2024-01-15T10:28:00Z",
            "run_attempt": 1,
        }
        
        run = WorkflowRun(**data)
        
        assert run.id == 12345
        assert run.name == "Deploy to Production"
        assert run.head_branch == "main"
        assert run.head_sha == "abc123def456"
        assert run.status == WorkflowRunStatus.COMPLETED
        assert run.conclusion == WorkflowRunConclusion.SUCCESS
    
    def test_workflow_job_model(self):
        """Test WorkflowJob model creation and validation."""
        data = {
            "id": 98765,
            "run_id": 12345,
            "name": "Deploy to Kubernetes",
            "status": "completed",
            "conclusion": "success",
            "started_at": "2024-01-15T10:28:00Z",
            "completed_at": "2024-01-15T10:35:00Z",
            "steps": [
                {"name": "Checkout", "status": "completed", "conclusion": "success"},
                {"name": "Build", "status": "completed", "conclusion": "success"},
                {"name": "Deploy", "status": "completed", "conclusion": "success"},
            ],
        }
        
        job = WorkflowJob(**data)
        
        assert job.id == 98765
        assert job.run_id == 12345
        assert job.name == "Deploy to Kubernetes"
        assert job.status == JobStatus.COMPLETED
        assert job.conclusion == JobConclusion.SUCCESS
        assert len(job.steps) == 3
    
    def test_commit_model(self):
        """Test Commit model creation and validation."""
        data = {
            "sha": "abc123def456789",
            "author": {
                "name": "John Doe",
                "email": "john@example.com",
                "date": "2024-01-15T09:45:00Z",
            },
            "committer": {
                "name": "John Doe",
                "email": "john@example.com",
                "date": "2024-01-15T09:45:00Z",
            },
            "message": "Fix memory limit configuration\n\nReduced memory limit from 1Gi to 512Mi",
            "url": "https://api.github.com/repos/owner/repo/commits/abc123",
            "parents": [{"sha": "parent123"}],
        }
        
        commit = Commit(**data)
        
        assert commit.sha == "abc123def456789"
        assert commit.author["name"] == "John Doe"
        assert commit.message.startswith("Fix memory limit")
    
    def test_deployment_status_model(self):
        """Test DeploymentStatus model creation and validation."""
        data = {
            "id": 55555,
            "state": "success",
            "target_url": "https://github.com/owner/repo/deployments/55555",
            "description": "Deployment to production",
            "environment": "production",
            "environment_url": "https://prod.example.com",
            "creator": {"login": "deploy-bot"},
            "created_at": "2024-01-15T10:28:00Z",
            "updated_at": "2024-01-15T10:35:00Z",
            "deployment": {
                "id": 55555,
                "sha": "abc123def456",
                "ref": "main",
                "task": "deploy",
                "environment": "production",
            },
            "repository": {"id": 123, "name": "payment-service", "full_name": "owner/payment-service"},
        }
        
        deployment = DeploymentStatus(**data)
        
        assert deployment.id == 55555
        assert deployment.state == "success"
        assert deployment.environment == "production"
    
    def test_github_actions_cicd_data_model(self):
        """Test GitHubActionsCICDData model."""
        from backend.data_sources.github_actions.models import WorkflowRun, WorkflowJob
        from datetime import datetime
        
        run = WorkflowRun(
            id=12345,
            name="Deploy",
            head_branch="main",
            head_sha="abc123",
            run_number=1,
            event="push",
            status=WorkflowRunStatus.COMPLETED,
            conclusion=WorkflowRunConclusion.SUCCESS,
            workflow_id=1,
            url="https://api.github.com/repos/owner/repo/actions/runs/1",
            html_url="https://github.com/owner/repo/actions/runs/1",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            run_started_at=datetime.now(),
            run_attempt=1,
        )
        
        cicd_data = GitHubActionsCICDData(
            workflow_runs=[run],
            workflow_jobs=[],
            commits=[],
            deployments=[],
            events=[],
            source="github_actions",
        )
        
        assert len(cicd_data.workflow_runs) == 1
        assert cicd_data.source == "github_actions"
        assert cicd_data.fetched_at is not None
    
    def test_agentops_cicd_data_model(self):
        """Test AgentOpsCICDData model (normalized output)."""
        cicd_data = AgentOpsCICDData(
            deployments=[{
                "deployment_id": "gh-12345",
                "timestamp": "2024-01-15T10:28:00Z",
                "service": "payment-service",
                "namespace": None,
                "image": None,
                "previous_image": None,
                "strategy": "github_actions",
                "replicas": None,
                "status": "success",
                "workflow_name": "Deploy to Production",
                "workflow_run_id": 12345,
                "commit_sha": "abc123",
                "branch": "main",
                "source": "github_actions_workflow",
            }],
            code_changes=[{
                "file": "config/memory.js",
                "description": "Reduced memory limit from 1Gi to 512Mi",
                "author": "dev-team",
                "commit": "a1b2c3d4",
                "timestamp": "2024-01-15T09:45:00Z",
                "commit_sha": "abc123",
                "source": "github_actions_commit",
            }],
            config_changes=[{
                "key": "resources.limits.memory",
                "old_value": None,
                "new_value": "workflow modified",
                "timestamp": "2024-01-15T09:45:00Z",
                "changed_by": "dev-team",
                "commit_sha": "a1b2c3d4",
                "source": "github_actions_workflow_change",
            }],
            dependency_changes=[{
                "name": "redis-client",
                "old_version": None,
                "new_version": None,
                "timestamp": "2024-01-15T09:45:00Z",
                "workflow_run_id": 12345,
                "source": "github_actions_dependabot",
            }],
            rollout_info={
                "type": "github_actions_workflow",
                "max_surge": None,
                "max_unavailable": None,
                "canary_percentage": None,
            },
        )
        
        assert len(cicd_data.deployments) == 1
        assert len(cicd_data.code_changes) == 1
        assert len(cicd_data.config_changes) == 1
        assert len(cicd_data.dependency_changes) == 1
        assert cicd_data.source == "github_actions"
        assert cicd_data.fetched_at is not None


class TestEnumValues:
    """Test enum values are correct."""
    
    def test_workflow_run_status(self):
        assert WorkflowRunStatus.QUEUED == "queued"
        assert WorkflowRunStatus.IN_PROGRESS == "in_progress"
        assert WorkflowRunStatus.COMPLETED == "completed"
    
    def test_workflow_run_conclusion(self):
        assert WorkflowRunConclusion.SUCCESS == "success"
        assert WorkflowRunConclusion.FAILURE == "failure"
        assert WorkflowRunConclusion.CANCELLED == "cancelled"
    
    def test_job_status(self):
        assert JobStatus.QUEUED == "queued"
        assert JobStatus.IN_PROGRESS == "in_progress"
        assert JobStatus.COMPLETED == "completed"
    
    def test_job_conclusion(self):
        assert JobConclusion.SUCCESS == "success"
        assert JobConclusion.FAILURE == "failure"
        assert JobConclusion.CANCELLED == "cancelled"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])