import pytest
from fastapi.testclient import TestClient

from app.api.v1.routes.chat import get_ollama_service
from app.core.config import get_settings
from app.main import create_app
from app.services.ollama_service import OllamaServiceError


class FakeOllamaService:
    async def generate(self, prompt: str, model: str) -> str:
        return f"echo: {prompt}"


class FailingOllamaService:
    async def generate(self, prompt: str, model: str) -> str:
        raise OllamaServiceError("boom")


def _client_with_fake_service(service_factory):
    app = create_app()
    app.dependency_overrides[get_ollama_service] = service_factory
    return TestClient(app)


def test_chat_success():
    with _client_with_fake_service(lambda: FakeOllamaService()) as client:
        response = client.post("/api/chat", json={"prompt": "hello"})
    assert response.status_code == 200
    assert response.json() == {"result": "echo: hello"}


def test_chat_upstream_failure_returns_500():
    with _client_with_fake_service(lambda: FailingOllamaService()) as client:
        response = client.post("/api/chat", json={"prompt": "hello"})
    assert response.status_code == 500


def test_chat_rejects_empty_prompt():
    with _client_with_fake_service(lambda: FakeOllamaService()) as client:
        response = client.post("/api/chat", json={"prompt": ""})
    assert response.status_code == 422


def test_chat_rejects_prompt_over_max_length(monkeypatch):
    monkeypatch.setenv("MAX_PROMPT_LENGTH", "5")
    get_settings.cache_clear()
    with _client_with_fake_service(lambda: FakeOllamaService()) as client:
        response = client.post("/api/chat", json={"prompt": "hello world"})
    assert response.status_code == 422


def test_chat_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    get_settings.cache_clear()
    with _client_with_fake_service(lambda: FakeOllamaService()) as client:
        unauthorized = client.post("/api/chat", json={"prompt": "hi"})
        assert unauthorized.status_code == 401

        authorized = client.post(
            "/api/chat", json={"prompt": "hi"}, headers={"X-API-Key": "secret"}
        )
        assert authorized.status_code == 200
