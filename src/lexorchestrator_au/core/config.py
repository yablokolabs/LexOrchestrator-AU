import logging
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "LexOrchestrator-AU"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    lex_api_keys: str = ""
    trust_proxy_headers: bool = False

    database_url: str = ""
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
    openai_embedding_max_batch: int = 2048

    llm_timeout_seconds: float = 25.0
    llm_retry_attempts: int = 3
    llm_retry_base_delay_seconds: float = 0.35
    llm_max_backoff_seconds: float = 30.0
    circuit_breaker_failure_threshold: int = 4
    circuit_breaker_recovery_seconds: float = 45.0

    anthropic_max_tokens: int = 4096
    unsupported_citation_confidence_cap: float = 0.55

    retrieval_limit: int = 12
    max_citations: int = 6
    cache_ttl_seconds: int = 900
    cache_max_entries: int = 10_000
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 20

    vector_weight: float = 0.70
    keyword_weight: float = 0.30

    supported_jurisdictions: list[str] = Field(default_factory=lambda: ["AU"])

    @property
    def parsed_api_keys(self) -> list[str]:
        return [item.strip() for item in self.lex_api_keys.split(",") if item.strip()]

    @field_validator("supported_jurisdictions")
    @classmethod
    def normalise_jurisdictions(cls, values: list[str]) -> list[str]:
        return [value.upper() for value in values]

    @model_validator(mode="after")
    def _validate_production_safety(self) -> "Settings":
        if self.app_env in ("staging", "production"):
            if "*" in self.cors_origins:
                raise ValueError(
                    "Wildcard CORS origin ('*') is not allowed in staging/production. "
                    "Set CORS_ORIGINS to explicit allowed origins."
                )
            if not self.parsed_api_keys:
                raise ValueError(
                    "API keys (LEX_API_KEYS) must be configured in staging/production."
                )
            if not self.database_url:
                raise ValueError("DATABASE_URL must be explicitly set in staging/production.")
        if not self.database_url:
            if self.app_env in ("staging", "production"):
                raise ValueError("DATABASE_URL must be explicitly set in staging/production.")
            self.database_url = "postgresql+asyncpg://localhost:5432/lexorchestrator"
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
