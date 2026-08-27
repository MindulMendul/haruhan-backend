import asyncio
import json

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


def test_list_models_returns_model_list(monkeypatch):
    def handler(request):
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:3b"}]})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    result = asyncio.run(service.list_models())
    assert result == [{"name": "qwen2.5:3b"}]


# HTTP 상태는 200으로 정상이지만 본문이 JSON이 아닌 경우(Ollama 앞단 프록시
# 오작동, 응답이 중간에 끊기는 경우 등)를 각 메서드마다 재현한다 - response.json()
# 호출이 try 블록 밖에 있으면 json.JSONDecodeError가 OllamaServiceError로 묶이지
# 않고 그대로 새어나가, 나머지 실패 경로(HTTP 에러)와 다르게 처리되지 않은
# 예외로 호출부까지 올라가는 버그였다.
def _malformed_json_handler(request):
    return httpx.Response(200, content=b"not json")


def test_generate_raises_ollama_service_error_on_malformed_json_body(monkeypatch):
    _install_mock_transport(monkeypatch, _malformed_json_handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    with pytest.raises(OllamaServiceError):
        asyncio.run(service.generate(prompt="안녕", model="qwen2.5:3b"))


def test_chat_raises_ollama_service_error_on_malformed_json_body(monkeypatch):
    _install_mock_transport(monkeypatch, _malformed_json_handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    with pytest.raises(OllamaServiceError):
        asyncio.run(service.chat(messages=[{"role": "user", "content": "안녕"}], model="qwen2.5:3b"))


def test_embed_raises_ollama_service_error_on_malformed_json_body(monkeypatch):
    _install_mock_transport(monkeypatch, _malformed_json_handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    with pytest.raises(OllamaServiceError):
        asyncio.run(service.embed(text="텍스트", model="nomic-embed-text"))


def test_list_models_raises_ollama_service_error_on_malformed_json_body(monkeypatch):
    _install_mock_transport(monkeypatch, _malformed_json_handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    with pytest.raises(OllamaServiceError):
        asyncio.run(service.list_models())


def test_generate_json_raises_ollama_service_error_on_malformed_json_body(monkeypatch):
    _install_mock_transport(monkeypatch, _malformed_json_handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    with pytest.raises(OllamaServiceError):
        asyncio.run(
            service.generate_json(prompt="프롬프트", model="qwen2.5:3b", schema={"type": "object"})
        )


def test_chat_stream_yields_content_in_order_and_stops_at_done(monkeypatch):
    """chat_stream()의 실제 ndjson 파싱 로직(빈 줄 건너뛰기, 청크별 content
    누적, done=true에서 멈추기)은 이 파일에서 여태 malformed-JSON 에러 경로
    하나로만 테스트되고 있었다 - study/interview-review 스트리밍 라우트
    테스트들은 전부 이 실제 구현을 통째로 갈아치우는 FakeOllamaService를 쓰기
    때문에, 정작 실제 Ollama와 통신하는 이 코드의 정상 동작 경로는 전체
    테스트 스위트 어디에서도 검증되지 않고 있었다. 실제 Ollama가 보내는
    형태(줄 사이 빈 줄 포함, done=true인 마지막 줄은 content가 비어있음)를
    흉내 낸 ndjson 스트림을 흘려보내, content가 순서대로만 yield되고
    (빈 content는 안 나오고) done을 만나면 정확히 거기서 멈추는지 확인한다."""
    lines = [
        json.dumps({"message": {"content": "안"}, "done": False}),
        "",  # 실제 Ollama 스트림에도 섞여 오는 빈 줄 - continue로 건너뛰어야 함
        json.dumps({"message": {"content": "녕"}, "done": False}),
        json.dumps({"message": {"content": ""}, "done": True}),
        # done 이후에도 줄이 더 올 수 있는 상황을 흉내낸다 - break가 없으면
        # 이 줄까지 읽어 "하세요"가 결과에 섞여 들어가 버린다.
        json.dumps({"message": {"content": "하세요"}, "done": False}),
    ]
    body = ("\n".join(lines) + "\n").encode("utf-8")

    def handler(request):
        assert request.url.path == "/api/chat"
        return httpx.Response(200, content=body)

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")

    async def _collect():
        return [
            chunk
            async for chunk in service.chat_stream(
                messages=[{"role": "user", "content": "안녕"}], model="qwen2.5:3b"
            )
        ]

    assert asyncio.run(_collect()) == ["안", "녕"]


def test_chat_stream_raises_ollama_service_error_on_malformed_json_line(monkeypatch):
    def handler(request):
        return httpx.Response(200, content=b"not json\n")

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")

    async def _drain():
        async for _ in service.chat_stream(
            messages=[{"role": "user", "content": "안녕"}], model="qwen2.5:3b"
        ):
            pass

    with pytest.raises(OllamaServiceError):
        asyncio.run(_drain())


# dict.get(key, default)는 key가 아예 없을 때만 default를 쓴다 - Ollama가(혹은
# 앞단 프록시가) `{"response": null}`처럼 key는 있는데 값이 JSON null인 응답을
# 주면 그대로 None이 반환되는 버그였다. 이 서비스의 반환 타입은 전부 str/list로
# 선언돼 있고 호출부(interview_practice_service.py 등)는 그 선언을 믿고
# `.strip()`을 곧바로 호출하므로, None이 새어나가면 AttributeError로 재시도 없이
# 그대로 죽어버린다.
def test_generate_returns_empty_string_when_response_is_explicit_null(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"response": None})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    result = asyncio.run(service.generate(prompt="안녕", model="qwen2.5:3b"))
    assert result == ""


def test_chat_returns_empty_string_when_content_is_explicit_null(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"message": {"role": "assistant", "content": None}})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    result = asyncio.run(
        service.chat(messages=[{"role": "user", "content": "안녕"}], model="qwen2.5:3b")
    )
    assert result == ""


def test_chat_returns_empty_string_when_message_itself_is_explicit_null(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"message": None})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    result = asyncio.run(
        service.chat(messages=[{"role": "user", "content": "안녕"}], model="qwen2.5:3b")
    )
    assert result == ""


def test_embed_returns_empty_list_when_embedding_is_explicit_null(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"embedding": None})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    result = asyncio.run(service.embed(text="텍스트", model="nomic-embed-text"))
    assert result == []


def test_generate_json_returns_empty_string_when_response_is_explicit_null(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"response": None})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    result = asyncio.run(
        service.generate_json(prompt="프롬프트", model="qwen2.5:3b", schema={"type": "object"})
    )
    assert result == ""


def test_list_models_returns_empty_list_when_models_is_explicit_null(monkeypatch):
    def handler(request):
        return httpx.Response(200, json={"models": None})

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")
    result = asyncio.run(service.list_models())
    assert result == []


def test_chat_stream_yields_nothing_when_content_is_explicit_null(monkeypatch):
    lines = [
        json.dumps({"message": {"content": None}, "done": False}),
        json.dumps({"message": None, "done": True}),
    ]
    body = ("\n".join(lines) + "\n").encode("utf-8")

    def handler(request):
        return httpx.Response(200, content=body)

    _install_mock_transport(monkeypatch, handler)
    service = OllamaService(base_url="http://fake-ollama:11434")

    async def _collect():
        return [
            chunk
            async for chunk in service.chat_stream(
                messages=[{"role": "user", "content": "안녕"}], model="qwen2.5:3b"
            )
        ]

    assert asyncio.run(_collect()) == []
