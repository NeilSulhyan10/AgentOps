import pytest
from datetime import datetime, timedelta
import httpx

from backend.data_sources.github_actions.client import (
    GitHubActionsClient,
    GitHubAPIError,
    RateLimitError,
)
from backend.data_sources.github_actions.models import (
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


class TestGitHubActionsClient:
    """Test GitHub Actions client."""
    
    @pytest.fixture
    def client(self):
        """Create a client with a test token."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}):
            return GitHubActionsClient(token="test-token")
    
    def test_init_requires_token(self):
        """Test that client requires a token."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="GitHub token is required"):
                GitHubActionsClient(token=None)
    
    def test_init_with_env_var(self):
        """Test client can use GITHUB_TOKEN from environment."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}):
            client = GitHubActionsClient()
            assert client.token == "env-token"
    
    @pytest.mark.asyncio
    async def test_get_workflow_runs_success(self, client):
        """Test successful workflow runs fetch."""
        mock_response = {
            "workflow_runs": [
                {
                    "id": 12345,
                    "name": "Deploy to Production",
                    "head_branch": "main",
                    "head_sha": "abc123",
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
            ]
        }
        
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            runs = await client.get_workflow_runs("owner", "repo")
            
            assert len(runs) == 1
            assert runs[0].id == 12345
            assert runs[0].name == "Deploy to Production"
    
    @pytest.mark.asyncio
    async def test_get_workflow_runs_rate_limit(self, client):
        """Test rate limit error handling."""
        from backend.data_sources.github_actions.client import RateLimitError
        
        mock_response = AsyncMock()
        mock_response.status_code = 403
        mock_response.headers = {"X-RateLimit-Reset": str(int((datetime.now() + timedelta(seconds=60)).timestamp()))}
        
        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            with pytest.raises(RateLimitError):
                await client.get_workflow_runs("owner", "repo")
    
    @pytest.mark.asyncio
    async def test_get_workflow_runs_unauthorized(self, client):
        """Test unauthorized error handling."""
        mock_response = AsyncMock()
        mock_response.status_code = 401
        
        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            with pytest.raises(GitHubAPIError, match="Invalid GitHub token"):
                await client.get_workflow_runs("owner", "repo")
    
    @pytest.mark.asyncio
    async def test_get_workflow_jobs(self, client):
        """Test workflow jobs fetch."""
        mock_response = {
            "jobs": [
                {
                    "id": 98765,
                    "run_id": 12345,
                    "name": "Deploy",
                    "status": "completed",
                    "conclusion": "success",
                    "started_at": "2024-01-15T10:28:00Z",
                    "completed_at": "2024-01-15T10:35:00Z",
                    "steps": [],
                }
            ]
        }
        
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            jobs = await client.get_workflow_jobs("owner", "repo", 12345)
            
            assert len(jobs) == 1
            assert jobs[0].id == 98765
    
    @pytest.mark.asyncio
    async def test_get_commits(self, client):
        """Test commit fetch."""
        mock_response = {
            "sha": "abc123",
            "author": {"name": "John", "email": "john@example.com", "date": "2024-01-15T10:00:00Z"},
            "committer": {"name": "John", "email": "john@example.com", "date": "2024-01-15T10:00:00Z"},
            "message": "Test commit",
            "url": "https://api.github.com/repos/owner/repo/commits/abc123",
        }
        
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            commit = await client.get_commits("owner", "repo", "abc123")
            
            assert commit.sha == "abc123"
            assert commit.author["name"] == "John"
    
    @pytest.mark.asyncio
    async def test_get_repository(self, client):
        """Test repository fetch."""
        mock_response = {
            "id": 123,
            "name": "test-repo",
            "full_name": "owner/test-repo",
            "owner": {"login": "owner"},
            "private": False,
            "html_url": "https://github.com/owner/test-repo",
            "description": "Test repo",
            "fork": False,
            "default_branch": "main",
        }
        
        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            repo = await client.get_repository("owner", "test-repo")
            
            assert repo.id == 123
            assert repo.name == "test-repo"
    
    @pytest.mark.asyncio
    async def test_fetch_cicd_data_for_incident(self, client):
        """Test fetching CI/CD data for an incident time window."""
        # Mock all the individual API calls
        workflow_runs = [{
            "id": 12345,
            "name": "Deploy to Production",
            "head_branch": "main",
            "head_sha": "abc123",
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
            "actor": {"login": "deploy-bot"},
        }]
        
        jobs = [{
            "id": 98765,
            "run_id": 12345,
            "name": "Deploy",
            "status": "completed",
            "conclusion": "success",
            "started_at": "2024-01-15T10:28:00Z",
            "completed_at": "2024-01-15T10:35:00Z",
            "steps": [],
        }]
        
        deployments = [{
            "id": 55555,
            "state": "success",
            "target_url": "https://github.com/owner/repo/deployments/55555",
            "description": "Deployment to production",
            "environment": "production",
            "environment_url": "https://prod.example.com",
            "creator": {"login": "deploy-bot"},
            "created_at": "2024-01-15T10:28:00Z",
            "updated_at": "2024-01-15T10:35:00Z",
            "deployment": {"id": 55555, "sha": "abc123", "ref": "main", "task": "deploy", "environment": "production"},
            "repository": {"id": 123, "name": "payment-service", "full_name": "owner/payment-service"},
        }]
        
        commits = [{
            "sha": "abc123",
            "author": {"name": "John", "email": "john@example.com", "date": "2024-01-15T10:00:00Z"},
            "committer": {"name": "John", "email": "john@example.com", "date": "2024-01-15T10:00:00Z"},
            "message": "Test commit",
            "url": "https://api.github.com/repos/owner/repo/commits/abc123",
        }]
        
        repo = {
            "id": 123,
            "name": "payment-service",
            "full_name": "owner/payment-service",
            "owner": {"login": "owner"},
            "private": False,
            "html_url": "https://github.com/owner/payment-service",
            "description": "Payment service",
            "fork": False,
            "default_branch": "main",
        }
        
        with patch.object(client, "get_workflow_runs", new_callable=AsyncMock) as mock_runs, \
             patch.object(client, "get_workflow_jobs", new_callable=AsyncMock) as mock_jobs, \
             patch.object(client, "get_deployments", new_callable=AsyncMock) as mock_deployments, \
             patch.object(client, "get_commits", new_callable=AsyncMock) as mock_commits, \
             patch.object(client, "get_repository", new_callable=AsyncMock) as mock_repo:
            
            mock_runs.return_value = [WorkflowRun(**r) for r in workflow_runs]
            mock_jobs.return_value = [WorkflowJob(**j) for j in jobs]
            mock_deployments.return_value = [DeploymentStatus(**d) for d in deployments]
            mock_commits.return_value = Commit(**commits[0])
            mock_repo.return_value = Repository(**repo)
            
            incident_time = datetime(2024, 1, 15, 10, 30, 0)
            result = await client.fetch_cicd_data_for_incident(
                owner="owner",
                repo="repo",
                incident_time=incident_time,
                time_window_hours=24,
            )
            
            assert len(result.workflow_runs) == 1
            assert len(result.workflow_jobs) == 1
            assert len(result.deployments) == 1
            assert len(result.commits) == 1
            assert result.repository is not None
            assert result.source == "github_actions"


class TestClientErrorHandling:
    """Test client error handling scenarios."""
    
    @pytest.fixture
    def client(self):
        with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}):
            return GitHubActionsClient(token="test-token")
    
    @pytest.mark.asyncio
    async def test_invalid_token(self, client):
        """Test handling of invalid token."""
        mock_response = AsyncMock()
        mock_response.status_code = 401
        
        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            with pytest.raises(GitHubAPIError, match="Invalid GitHub token"):
                await client.get_workflow_runs("owner", "repo")
    
    @pytest.mark.asyncio
    async def test_not_found(self, client):
        """Test 404 handling."""
        mock_response = AsyncMock()
        mock_response.status_code = 404
        
        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            with pytest.raises(GitHubAPIError, match="Resource not found"):
                await client.get_workflow_runs("owner", "nonexistent")
    
    @pytest.mark.asyncio
    async def test_server_error(self, client):
        """Test 5xx error handling."""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        
        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            with pytest.raises(GitHubAPIError, match="GitHub API error: 500"):
                await client.get_workflow_runs("owner", "repo")
    
    @pytest.mark.asyncio
    async def test_network_timeout(self, client):
        """Test timeout handling."""
        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Timeout")
            
            with pytest.raises(httpx.TimeoutException):
                await client.get_workflow_runs("owner", "repo")
    
    @pytest.mark.asyncio
    async def test_connection_error(self, client):
        """Test connection error handling."""
        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("Connection refused")
            
            with pytest.raises(httpx.ConnectError):
                await client.get_workflow_runs("owner", "repo")


class TestRealDataOnly:
    """Test that only real GitHub Actions data is used (no mock fallback)."""
    
    def test_no_mock_cicd_fixtures_exist(self):
        """Test that no mock CI/CD fixture files exist."""
        from pathlib import Path
        cicd_dir = Path("/home/neil/Documents/Project/agentops/data/cicd")
        json_files = list(cicd_dir.glob("*.json"))
        assert len(json_files) == 0, f"Found mock CI/CD files: {json_files}"
    
    def test_data_source_config_removed(self):
        """Test that DATA_SOURCE config is removed."""
        from backend.config import Settings
        test_settings = Settings()
        assert not hasattr(test_settings, "data_source")
        assert hasattr(test_settings, "github_token")
        assert hasattr(test_settings, "github_owner")
        assert hasattr(test_settings, "github_repo")
        assert hasattr(test_settings, "github_branch")
        assert hasattr(test_settings, "github_time_window_hours")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])