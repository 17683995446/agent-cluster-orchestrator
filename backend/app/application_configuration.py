from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    APP_NAME: str = "Agent Cluster Orchestrator"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_cluster"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    DEFAULT_MODEL: str = "gpt-4"
    DEFAULT_PROVIDER: Literal["openai", "anthropic", "local"] = "openai"

    MAX_CONCURRENT_TASKS: int = 10
    TASK_TIMEOUT: int = 300
    HEARTBEAT_INTERVAL: int = 30
    MAX_RETRIES: int = 3

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"

    PROMETHEUS_ENABLED: bool = True

    SENTRY_DSN: str = ""

    @property
    def is_production(self) -> bool:
        return not self.DEBUG

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
