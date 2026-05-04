from fastapi.testclient import TestClient

from lexorchestrator_au.core.config import get_settings
from lexorchestrator_au.main import create_app

_TEST_API_KEY = "test-key-that-is-long-enough"


def test_api_key_protects_query_but_not_public_routes(monkeypatch) -> None:
    """Public routes (/health, /metrics) never require auth; protected routes do."""
    monkeypatch.setenv("LEX_API_KEYS", _TEST_API_KEY)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://lex:lex@127.0.0.1:65432/lexorchestrator"
    )
    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            assert client.get("/health").status_code == 200
            assert client.get("/metrics").status_code == 200
            # Protected endpoint requires API key
            resp = client.post("/v1/query", json={"question": "test"})
            assert resp.status_code == 401
            resp = client.post(
                "/v1/query",
                json={"question": "test"},
                headers={"x-api-key": _TEST_API_KEY},
            )
            # Should pass auth (422 = validation error, not 401)
            assert resp.status_code != 401
    finally:
        get_settings.cache_clear()
