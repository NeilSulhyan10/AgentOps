from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class WorkflowRunStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class WorkflowRunConclusion(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"


class JobStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class JobConclusion(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"


class WorkflowRun(BaseModel):
    id: int
    name: str
    head_branch: str
    head_sha: str
    run_number: int
    event: str
    status: WorkflowRunStatus
    conclusion: Optional[WorkflowRunConclusion]
    workflow_id: int
    url: str
    html_url: str
    created_at: datetime
    updated_at: datetime
    run_started_at: Optional[datetime]
    run_attempt: int
    actor: Optional[Dict[str, Any]] = None
    repository: Optional[Dict[str, Any]] = None
    head_repository: Optional[Dict[str, Any]] = None
    triggering_actor: Optional[Dict[str, Any]] = None


class WorkflowJob(BaseModel):
    id: int
    run_id: int
    name: str
    status: JobStatus
    conclusion: Optional[JobConclusion]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    runner_id: Optional[int] = None
    runner_name: Optional[str] = None
    runner_group_id: Optional[int] = None
    runner_group_name: Optional[str] = None


class WorkflowJobLog(BaseModel):
    name: str
    steps: List[Dict[str, Any]] = Field(default_factory=list)


class Commit(BaseModel):
    sha: str
    author: Dict[str, Any]
    committer: Dict[str, Any]
    message: Optional[str] = ""
    url: str
    parents: List[Dict[str, Any]] = Field(default_factory=list)
    verification: Optional[Dict[str, Any]] = None


class DeploymentStatus(BaseModel):
    id: int
    state: str
    target_url: Optional[str]
    description: Optional[str]
    environment: str
    environment_url: Optional[str]
    creator: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deployment: Dict[str, Any]
    repository: Dict[str, Any]
    statuses: List[Dict[str, Any]] = Field(default_factory=list)


class Repository(BaseModel):
    id: int
    name: str
    full_name: str
    owner: Dict[str, Any]
    private: bool
    html_url: str
    description: Optional[str]
    fork: bool
    default_branch: str


class GitHubEventData(BaseModel):
    event_type: str
    payload: Dict[str, Any]
    created_at: datetime
    repo: Optional[Repository] = None
    actor: Optional[Dict[str, Any]] = None


class GitHubActionsCICDData(BaseModel):
    workflow_runs: List[WorkflowRun] = Field(default_factory=list)
    workflow_jobs: List[WorkflowJob] = Field(default_factory=list)
    commits: List[Commit] = Field(default_factory=list)
    deployments: List[DeploymentStatus] = Field(default_factory=list)
    events: List[GitHubEventData] = Field(default_factory=list)
    repository: Optional[Repository] = None
    source: str = "github_actions"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


class AgentOpsCICDData(BaseModel):
    deployments: List[Dict[str, Any]] = Field(default_factory=list)
    code_changes: List[Dict[str, Any]] = Field(default_factory=list)
    config_changes: List[Dict[str, Any]] = Field(default_factory=list)
    dependency_changes: List[Dict[str, Any]] = Field(default_factory=list)
    rollout_info: Dict[str, Any] = Field(default_factory=dict)
    source: str = "github_actions"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    raw_data: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = True