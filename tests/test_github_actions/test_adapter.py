import pytest
from datetime import datetime
from backend.data_sources.github_actions.models import (
    GitHubActionsCICDData,
    WorkflowRun,
    WorkflowJob,
    Commit,
    DeploymentStatus,
    Repository,
    WorkflowRunStatus,
    WorkflowRunConclusion,
    JobStatus,
    JobConclusion,
)
from backend.data_sources.github_actions.adapter import GitHubActionsAdapter, normalize_to_agentops_cicd_schema


class TestGitHubActionsAdapter:
    """Test the GitHub Actions adapter."""
    
    @pytest.fixture
    def sample_github_data(self):
        """Create sample GitHub Actions data for testing."""
        run = WorkflowRun(
            id=12345,
            name="Deploy to Production",
            head_branch="main",
            head_sha="abc123def456",
            run_number=42,
            event="push",
            status=WorkflowRunStatus.COMPLETED,
            conclusion=WorkflowRunConclusion.SUCCESS,
            workflow_id=67890,
            url="https://api.github.com/repos/owner/repo/actions/runs/12345",
            html_url="https://github.com/owner/repo/actions/runs/12345",
            created_at=datetime(2024, 1, 15, 10, 28, 0),
            updated_at=datetime(2024, 1, 15, 10, 35, 0),
            run_started_at=datetime(2024, 1, 15, 10, 28, 0),
            run_attempt=1,
            actor={"login": "deploy-bot"},
        )
        
        job = WorkflowJob(
            id=98765,
            run_id=12345,
            name="Deploy to Kubernetes",
            status=JobStatus.COMPLETED,
            conclusion=JobConclusion.SUCCESS,
            started_at=datetime(2024, 1, 15, 10, 28, 0),
            completed_at=datetime(2024, 1, 15, 10, 35, 0),
            steps=[
                {"name": "Checkout", "status": "completed", "conclusion": "success"},
                {"name": "Build", "status": "completed", "conclusion": "success"},
                {"name": "Deploy", "status": "completed", "conclusion": "success"},
            ],
        )
        
        commit = Commit(
            sha="abc123def456789",
            author={
                "name": "John Doe",
                "email": "john@example.com",
                "date": "2024-01-15T09:45:00Z",
            },
            committer={
                "name": "John Doe",
                "email": "john@example.com",
                "date": "2024-01-15T09:45:00Z",
            },
            message="Fix memory limit configuration\n\nReduced memory limit from 1Gi to 512Mi",
            url="https://api.github.com/repos/owner/repo/commits/abc123",
        )
        
        deployment = DeploymentStatus(
            id=55555,
            state="success",
            target_url="https://github.com/owner/repo/deployments/55555",
            description="Deployment to production",
            environment="production",
            environment_url="https://prod.example.com",
            creator={"login": "deploy-bot"},
            created_at=datetime(2024, 1, 15, 10, 28, 0),
            updated_at=datetime(2024, 1, 15, 10, 35, 0),
            deployment={
                "id": 55555,
                "sha": "abc123def456",
                "ref": "main",
                "task": "deploy",
                "environment": "production",
            },
            repository={"id": 123, "name": "payment-service", "full_name": "owner/payment-service"},
            statuses=[],
        )
        
        repo = Repository(
            id=123,
            name="payment-service",
            full_name="owner/payment-service",
            owner={"login": "owner"},
            private=False,
            html_url="https://github.com/owner/payment-service",
            description="Payment service",
            fork=False,
            default_branch="main",
        )
        
        return GitHubActionsCICDData(
            workflow_runs=[run],
            workflow_jobs=[job],
            commits=[commit],
            deployments=[deployment],
            repository=repo,
            source="github_actions",
        )
    
    def test_adapter_basic_transformation(self, sample_github_data):
        """Test basic transformation from GitHub data to AgentOps schema."""
        adapter = GitHubActionsAdapter()
        result = adapter.adapt(sample_github_data)
        
        assert result.source == "github_actions"
        assert result.fetched_at is not None
        assert len(result.deployments) >= 1
    
    def test_deployment_extraction(self, sample_github_data):
        """Test deployment extraction from workflow runs."""
        adapter = GitHubActionsAdapter()
        result = adapter.adapt(sample_github_data)
        
        assert len(result.deployments) >= 1
        dep = result.deployments[0]
        
        # Check required fields
        assert "deployment_id" in dep
        assert "timestamp" in dep
        assert "service" in dep
        assert "namespace" in dep
        assert "image" in dep
        assert "previous_image" in dep
        assert "strategy" in dep
        assert "replicas" in dep
        assert "status" in dep
        assert "workflow_name" in dep
        assert "workflow_run_id" in dep
        assert "commit_sha" in dep
        assert "branch" in dep
        assert "source" in dep
        
        # Check unavailable fields are None
        assert dep["namespace"] is None
        assert dep["image"] is None
        assert dep["previous_image"] is None
        assert dep["replicas"] is None
        
        # Check available fields
        assert dep["service"] == "payment-service"
        assert dep["commit_sha"] == "abc123def456"
        assert dep["branch"] == "main"
        assert dep["status"] == "success"
        assert dep["source"] in ["github_actions_workflow", "github_actions_deployment"]
    
    def test_code_changes_extraction(self, sample_github_data):
        """Test code changes extraction."""
        adapter = GitHubActionsAdapter()
        result = adapter.adapt(sample_github_data)
        
        # Code changes depend on commit file extraction (not implemented)
        # Should return empty list or handle gracefully
        assert isinstance(result.code_changes, list)
    
    def test_config_changes_extraction(self, sample_github_data):
        """Test config changes extraction."""
        adapter = GitHubActionsAdapter()
        result = adapter.adapt(sample_github_data)
        
        assert isinstance(result.config_changes, list)
        # Config changes depend on workflow file parsing (not implemented)
    
    def test_dependency_changes_extraction(self, sample_github_data):
        """Test dependency changes extraction."""
        adapter = GitHubActionsAdapter()
        result = adapter.adapt(sample_github_data)
        
        assert isinstance(result.dependency_changes, list)
    
    def test_rollout_info_extraction(self, sample_github_data):
        """Test rollout info extraction."""
        adapter = GitHubActionsAdapter()
        result = adapter.adapt(sample_github_data)
        
        assert "type" in result.rollout_info
        assert "max_surge" in result.rollout_info
        assert "max_unavailable" in result.rollout_info
        assert "canary_percentage" in result.rollout_info
        
        # These should be None as they're K8s-specific
        assert result.rollout_info["max_surge"] is None
        assert result.rollout_info["max_unavailable"] is None
        assert result.rollout_info["canary_percentage"] is None
        assert result.rollout_info["type"] == "github_actions_workflow"
    
    def test_convenience_function(self, sample_github_data):
        """Test the convenience normalize_to_agentops_cicd_schema function."""
        result = normalize_to_agentops_cicd_schema(sample_github_data)
        
        assert result.source == "github_actions"
        assert result.fetched_at is not None
        assert isinstance(result.deployments, list)
        assert isinstance(result.code_changes, list)
        assert isinstance(result.config_changes, list)
        assert isinstance(result.dependency_changes, list)
        assert isinstance(result.rollout_info, dict)
    
    def test_raw_data_inclusion(self, sample_github_data):
        """Test raw data inclusion when enabled."""
        adapter = GitHubActionsAdapter(include_raw_data=True)
        result = adapter.adapt(sample_github_data)
        
        assert result.raw_data is not None
        assert "workflow_runs" in result.raw_data
        assert "workflow_jobs" in result.raw_data
        assert "commits" in result.raw_data
        assert "deployments" in result.raw_data
    
    def test_raw_data_exclusion(self, sample_github_data):
        """Test raw data exclusion by default."""
        adapter = GitHubActionsAdapter(include_raw_data=False)
        result = adapter.adapt(sample_github_data)
        
        assert result.raw_data is None
    
    def test_multiple_workflow_runs(self, sample_github_data):
        """Test handling of multiple workflow runs."""
        from backend.data_sources.github_actions.models import WorkflowRun, WorkflowRunStatus, WorkflowRunConclusion
        
        # Add another workflow run
        run2 = WorkflowRun(
            id=12346,
            name="Deploy to Staging",
            head_branch="main",
            head_sha="def456ghi789",
            run_number=43,
            event="push",
            status=WorkflowRunStatus.COMPLETED,
            conclusion=WorkflowRunConclusion.SUCCESS,
            workflow_id=67890,
            url="https://api.github.com/repos/owner/repo/actions/runs/12346",
            html_url="https://github.com/owner/repo/actions/runs/12346",
            created_at=datetime(2024, 1, 15, 11, 0, 0),
            updated_at=datetime(2024, 1, 15, 11, 10, 0),
            run_started_at=datetime(2024, 1, 15, 11, 0, 0),
            run_attempt=1,
        )
        
        sample_github_data.workflow_runs.append(run2)
        
        adapter = GitHubActionsAdapter()
        result = adapter.adapt(sample_github_data)
        
        assert len(result.deployments) >= 2
        # Both should be deployment-related
        deployment_names = [d.get("workflow_name", "") for d in result.deployments]
        assert "Deploy to Production" in deployment_names
        assert "Deploy to Staging" in deployment_names
    
    def test_failed_workflow_run_handling(self, sample_github_data):
        """Test handling of failed workflow runs."""
        from backend.data_sources.github_actions.models import WorkflowRun, WorkflowRunStatus, WorkflowRunConclusion
        
        # Add a failed run
        failed_run = WorkflowRun(
            id=12347,
            name="Deploy to Production",
            head_branch="main",
            head_sha="ghi789jkl012",
            run_number=44,
            event="push",
            status=WorkflowRunStatus.COMPLETED,
            conclusion=WorkflowRunConclusion.FAILURE,
            workflow_id=67890,
            url="https://api.github.com/repos/owner/repo/actions/runs/12347",
            html_url="https://github.com/owner/repo/actions/runs/12347",
            created_at=datetime(2024, 1, 15, 12, 0, 0),
            updated_at=datetime(2024, 1, 15, 12, 10, 0),
            run_started_at=datetime(2024, 1, 15, 12, 0, 0),
            run_attempt=1,
        )
        
        sample_github_data.workflow_runs.append(failed_run)
        
        adapter = GitHubActionsAdapter()
        result = adapter.adapt(sample_github_data)
        
        # Should include failed deployment
        failed_deployments = [d for d in result.deployments if d.get("status") == "failure"]
        assert len(failed_deployments) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])