from fastapi.testclient import TestClient

from lexorchestrator_au.core.config import get_settings
from lexorchestrator_au.main import create_app


def test_api_key_protects_metrics_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("LEX_API_KEYS", "test-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://lex:lex@127.0.0.1:65432/lexorchestrator")
    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            assert client.get("/health").status_code == 200
            assert client.get("/metrics").status_code == 401
            assert client.get("/metrics", headers={"x-api-key": "test-key"}).status_code == 200
    finally:
        get_settings.cache_clear()
