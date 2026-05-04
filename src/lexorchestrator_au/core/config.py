from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "LexOrchestrator-AU"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    lex_api_keys: str = ""
    trust_proxy_headers: bool = False

    database_url: str = "postgresql+asyncpg://lex:lex@localhost:5432/lexorchestrator"
    auto_create_schema: bool = True
    redis_url: str | None = None

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    llama_api_url: str | None = None

    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-3-5-sonnet-latest"
    llama_model: str = "llama-3.1-8b-instruct"

    embedding_provider: Literal["hash", "openai"] = "hash"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 384
    embedding_batch_size: int = 64

    llm_timeout_seconds: float = 25.0
    llm_retry_attempts: int = 3
    llm_retry_base_delay_seconds: float = 0.35
    circuit_breaker_failure_threshold: int = 4
    circuit_breaker_recovery_seconds: float = 45.0

    retrieval_limit: int = 12
    max_citations: int = 6
    cache_ttl_seconds: int = 900
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 20

    supported_jurisdictions: list[str] = Field(default_factory=lambda: ["AU"])

    @property
    def parsed_api_keys(self) -> list[str]:
        return [item.strip() for item in self.lex_api_keys.split(",") if item.strip()]

    @field_validator("supported_jurisdictions")
    @classmethod
    def normalise_jurisdictions(cls, values: list[str]) -> list[str]:
        return [value.upper() for value in values]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
