import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_ollama_service
from app.core.config import get_settings
from app.main import create_app
from app.services.ollama_service import OllamaServiceError


class FakeOllamaService:
    def __init__(self):
        self.generate_call_count = 0

    async def generate(self, prompt: str, model: str) -> str:
        self.generate_call_count += 1
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
        response = client.post("/api/v1/chat", json={"prompt": "hello"})
    assert response.status_code == 200
    assert response.json() == {"result": "echo: hello"}


def test_chat_upstream_failure_returns_502():
    with _client_with_fake_service(lambda: FailingOllamaService()) as client:
        response = client.post("/api/v1/chat", json={"prompt": "hello"})
    assert response.status_code == 502


def test_chat_rejects_empty_prompt():
    with _client_with_fake_service(lambda: FakeOllamaService()) as client:
        response = client.post("/api/v1/chat", json={"prompt": ""})
    assert response.status_code == 422


def test_chat_rejects_whitespace_only_prompt():
    """min_length=1은 빈 문자열만 막을 뿐 공백만 있는 값은 통과시킨다 - 통과하면
    무의미한 프롬프트로 Ollama 호출만 낭비하게 된다. 121/151라운드가 다른
    프롬프트 필드에 이미 추가한 검증이 이 엔드포인트에만 빠져 있었다."""
    fake = FakeOllamaService()
    with _client_with_fake_service(lambda: fake) as client:
        response = client.post("/api/v1/chat", json={"prompt": "   "})
    assert response.status_code == 422
    assert fake.generate_call_count == 0


def test_chat_rejects_prompt_over_max_length(monkeypatch):
    monkeypatch.setenv("MAX_PROMPT_LENGTH", "5")
    get_settings.cache_clear()
    with _client_with_fake_service(lambda: FakeOllamaService()) as client:
        response = client.post("/api/v1/chat", json={"prompt": "hello world"})
    assert response.status_code == 422


def test_chat_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    get_settings.cache_clear()
    with _client_with_fake_service(lambda: FakeOllamaService()) as client:
        unauthorized = client.post("/api/v1/chat", json={"prompt": "hi"})
        assert unauthorized.status_code == 401

        authorized = client.post(
            "/api/v1/chat", json={"prompt": "hi"}, headers={"X-API-Key": "secret"}
        )
        assert authorized.status_code == 200
