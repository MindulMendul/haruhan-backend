from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_security_headers_present(client):
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_docs_enabled_in_development(client):
    response = client.get("/docs")
    assert response.status_code == 200


def test_docs_disabled_in_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        response = test_client.get("/docs")
    assert response.status_code == 404
