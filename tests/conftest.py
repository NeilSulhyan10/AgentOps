"""Test setup: every test runs offline and writes its flow log to a temp file."""

import pytest

from backend.config import settings
from backend.llm import reset_llm_provider


@pytest.fixture(autouse=True)
def offline_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "rules")
    monkeypatch.setattr(settings, "fault_injection", "")
    monkeypatch.setattr(settings, "github_token", None)
    monkeypatch.setattr(settings, "flow_log_path", str(tmp_path / "flow.jsonl"))
    reset_llm_provider()
    yield
    reset_llm_provider()
