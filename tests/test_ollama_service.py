import asyncio

import httpx
import pytest

from app.services.ollama_service import OllamaService, OllamaServiceError


def _install_mock_transport(monkeypatch, handler):
    """httpx.AsyncClient가 실제 네트워크 대신 handler로 요청을 처리하게 한다.

    OllamaService는 각 메서드 안에서 매번 새 httpx.AsyncClient를 만들기 때문에,
    생성자를 몽키패치해서 항상 MockTransport를 끼워 넣는 방식으로 가로챈다.
    """
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


def test_generate_returns_response_text(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/generate"
        return httpx.Response(200, json={"response": "안녕하세요"})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    result = asyncio.run(service.generate(prompt="안녕", model="qwen2.5:3b"))
    assert result == "안녕하세요"


def test_generate_raises_ollama_service_error_on_http_error(monkeypatch):
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    with pytest.raises(OllamaServiceError):
        asyncio.run(service.generate(prompt="안녕", model="qwen2.5:3b"))


def test_chat_returns_message_content(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "반갑습니다"}})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    result = asyncio.run(
        service.chat(messages=[{"role": "user", "content": "안녕"}], model="qwen2.5:3b")
    )
    assert result == "반갑습니다"


def test_chat_raises_ollama_service_error_on_connect_error(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    with pytest.raises(OllamaServiceError):
        asyncio.run(service.chat(messages=[{"role": "user", "content": "안녕"}], model="qwen2.5:3b"))


def test_embed_returns_embedding_vector(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/embeddings"
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    result = asyncio.run(service.embed(text="텍스트", model="nomic-embed-text"))
    assert result == [0.1, 0.2, 0.3]


def test_embed_raises_ollama_service_error_on_http_error(monkeypatch):
    def handler(request):
        return httpx.Response(503, json={})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    with pytest.raises(OllamaServiceError):
        asyncio.run(service.embed(text="텍스트", model="nomic-embed-text"))


def test_generate_json_returns_response_text(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/generate"
        return httpx.Response(200, json={"response": '{"foo": "bar"}'})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    result = asyncio.run(
        service.generate_json(prompt="프롬프트", model="qwen2.5:3b", schema={"type": "object"})
    )
    assert result == '{"foo": "bar"}'


def test_generate_json_raises_ollama_service_error_on_http_error(monkeypatch):
    def handler(request):
        return httpx.Response(500, json={})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    with pytest.raises(OllamaServiceError):
        asyncio.run(
            service.generate_json(prompt="프롬프트", model="qwen2.5:3b", schema={"type": "object"})
        )
