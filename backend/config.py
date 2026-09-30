from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os


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

    llm_provider: str = "mock"
    nemotron_api_key: Optional[str] = None
    nemotron_api_url: Optional[str] = None
    nemotron_model: str = "nemotron-3-ultra"
    nemotron_max_tokens: int = 4096
    nemotron_temperature: float = 0.1

    max_iterations: int = 5
    confidence_threshold: float = 0.75
    enable_llm_routing: bool = False

    evaluation_dataset_path: str = "/app/data/ground_truth"
    evaluation_output_path: str = "/app/evaluation/experiments"
    data_dir: str = "/app/data"

    enable_tracing: bool = False
    otel_exporter_otlp_endpoint: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()