import pytest

from lexorchestrator_au.core.config import Settings


class TestSettings:
    def test_defaults(self) -> None:
        s = Settings(database_url="postgresql+asyncpg://x:x@localhost/db")
        assert s.app_env == "development"
        assert s.embedding_dimensions == 384

    def test_production_requires_api_keys(self) -> None:
        with pytest.raises(ValueError, match="API keys"):
            Settings(
                app_env="production",
                database_url="postgresql+asyncpg://x:x@localhost/db",
                cors_origins=["https://example.com"],
                lex_api_keys="",
            )

    def test_production_rejects_wildcard_cors(self) -> None:
        with pytest.raises(ValueError, match="Wildcard CORS"):
            Settings(
                app_env="production",
                database_url="postgresql+asyncpg://x:x@localhost/db",
                lex_api_keys="a]secret-key-12345678",
            )

    def test_parsed_api_keys(self) -> None:
        s = Settings(
            database_url="postgresql+asyncpg://x:x@localhost/db",
            lex_api_keys="key1, key2, ,key3",
        )
        assert s.parsed_api_keys == ["key1", "key2", "key3"]

    def test_dev_mode_allows_wildcard_cors(self) -> None:
        s = Settings(database_url="postgresql+asyncpg://x:x@localhost/db")
        assert s.cors_origins == ["*"]
