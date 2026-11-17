"""
Settings: every value can be overridden by an environment variable or by `.env`.

Defaults are chosen so that a fresh clone works with no `.env` at all: no LLM
(rule-based decisions), fixture data from `<repo>/data`, logs in `<repo>/logs`.
"""

import logging
from pathlib import Path
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "AgentOps"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "DEBUG"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "agentops"
    mongodb_max_pool_size: int = 10

    # Who makes the decisions: "rules" (no LLM, offline, deterministic) or "nemotron".
    llm_provider: str = "rules"
    nemotron_api_key: Optional[str] = None
    nemotron_api_url: Optional[str] = None
    nemotron_model: str = "nemotron-3-ultra"
    nemotron_max_tokens: int = 4096
    nemotron_temperature: float = 0.1
    llm_trace_enabled: bool = False
    llm_trace_path: str = str(REPO_ROOT / "logs" / "llm_traces.jsonl")

    # Flow log: one JSON line per investigation step (see backend/flow/log.py).
    langfuse_public_key: str = ""      # set both keys to send every LLM call to Langfuse (optional)
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3001"
    stale_run_minutes: int = 5           # a pending/running investigation not updated for this long is marked interrupted
    flow_log_enabled: bool = True
    flow_log_path: str = str(REPO_ROOT / "logs" / "flow.jsonl")
    # Break one part of AgentOps on purpose (see backend/faults.py). Empty = off.
    fault_injection: str = ""

    max_iterations: int = 5
    confidence_threshold: float = 0.75
    enable_critic: bool = True
    critic_max_rounds: int = 3

    data_dir: str = str(REPO_ROOT / "data")

    # GitHub Actions monitor: only needed to pick up real failed workflow runs.
    github_token: Optional[str] = None
    github_owner: Optional[str] = None
    github_repo: Optional[str] = None
    github_branch: Optional[str] = None
    github_time_window_hours: int = 24
    github_poll_interval_seconds: int = 60

    class Config:
        env_file = str(REPO_ROOT / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"   # old .env files may still carry settings that no longer exist

    @model_validator(mode="after")
    def _use_repo_data_when_data_dir_is_missing(self) -> "Settings":
        """A DATA_DIR copied from another machine must not silently empty the scenario list."""
        if not Path(self.data_dir).is_dir():
            fallback = REPO_ROOT / "data"
            logger.warning("DATA_DIR '%s' does not exist; using '%s' instead.", self.data_dir, fallback)
            self.data_dir = str(fallback)
        return self


settings = Settings()
