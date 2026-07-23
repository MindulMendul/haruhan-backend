from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_body_size_limit_rejects_large_payload(monkeypatch):
    monkeypatch.setenv("MAX_BODY_SIZE_BYTES", "10")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat", json={"prompt": "this payload is definitely longer than 10 bytes"}
        )
    assert response.status_code == 413


def test_body_size_limit_allows_small_payload(monkeypatch):
    monkeypatch.setenv("MAX_BODY_SIZE_BYTES", "1048576")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
