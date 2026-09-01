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


class BlankThenSucceedOllamaService:
    """ollama_service.generate()는 Ollama가 200을 응답해도 response 키가 없거나
    모델이 빈/공백 텍스트만 뱉으면 예외 없이 그냥 빈 문자열을 돌려준다 - 첫
    시도는 공백만 주고, 재시도에서만 성공하는 흐름을 재현한다."""

    def __init__(self):
        self.generate_call_count = 0

    async def generate(self, prompt: str, model: str) -> str:
        self.generate_call_count += 1
        if self.generate_call_count == 1:
            return "   "
        return f"echo: {prompt}"


class AlwaysBlankOllamaService:
    def __init__(self):
        self.generate_call_count = 0

    async def generate(self, prompt: str, model: str) -> str:
        self.generate_call_count += 1
        return ""


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


def test_chat_retries_once_and_recovers_from_blank_response():
    """208라운드: ollama_service.generate()가 예외 없이 빈/공백 문자열만
    돌려주는 경우(모델이 정말 빈 답을 했거나, 응답 본문에 response 키가
    없는 경우), 188라운드가 study_service/interview_practice_service 등
    다른 모든 generate()/chat() 호출부에 이미 적용한 것과 같은 재시도+공백
    검증이 이 범용 프록시 엔드포인트에도 적용됐는지 확인한다 - 첫 시도가
    공백이어도 재시도에서 성공하면 그 결과를 그대로 돌려줘야 한다."""
    fake = BlankThenSucceedOllamaService()
    with _client_with_fake_service(lambda: fake) as client:
        response = client.post("/api/v1/chat", json={"prompt": "hello"})
    assert response.status_code == 200
    assert response.json() == {"result": "echo: hello"}
    assert fake.generate_call_count == 2


def test_chat_returns_502_after_exhausting_retries_on_blank_response():
    """위 테스트와 같은 이유 - 재시도를 다 써도 계속 공백만 나오면, 200
    { "result": "" }로 조용히 성공한 것처럼 응답하는 대신 다른 생성 실패와
    같은 502로 응답해야 한다."""
    fake = AlwaysBlankOllamaService()
    with _client_with_fake_service(lambda: fake) as client:
        response = client.post("/api/v1/chat", json={"prompt": "hello"})
    assert response.status_code == 502
    assert fake.generate_call_count == 2


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


def test_chat_rejects_invisible_only_prompt():
    """`str.strip()`은 공백류만 제거하고 zero-width space(U+200B) 같은 유니코드
    Cf 카테고리 문자는 제거하지 못한다 - 이런 문자로만 이루어진 prompt가
    공백-only 검사를 통과해 Ollama 호출을 낭비시켰다."""
    fake = FakeOllamaService()
    with _client_with_fake_service(lambda: fake) as client:
        response = client.post("/api/v1/chat", json={"prompt": "​​"})
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
