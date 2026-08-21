import pytest

from app.core.dependencies import get_ollama_service
from app.services.ollama_service import OllamaServiceError


class FakeOllamaService:
    async def chat(self, messages, model):
        return f"assistant reply to: {messages[-1]['content']}"

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]

    async def chat_stream(self, messages, model):
        for chunk in ["안녕", "하세요"]:
            yield chunk


class FailingOllamaService:
    async def chat(self, messages, model):
        raise OllamaServiceError("boom")

    async def chat_stream(self, messages, model):
        raise OllamaServiceError("boom")
        yield ""  # pragma: no cover - async generator 문법상 필요 (도달 안 함)


def _signup_and_get_token(client, email="study@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "supersecret"}
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_and_list_sessions(client):
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/study/sessions", json={"title": "OS 프로세스"}, headers=_auth_headers(token)
    )
    assert create.status_code == 201
    body = create.json()
    assert body["title"] == "OS 프로세스"
    assert body["model"] == "qwen2.5:3b"

    listing = client.get("/api/v1/study/sessions", headers=_auth_headers(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_list_sessions_pagination(client):
    token = _signup_and_get_token(client)
    for i in range(5):
        client.post(
            "/api/v1/study/sessions", json={"title": f"세션 {i}"}, headers=_auth_headers(token)
        )

    first_page = client.get(
        "/api/v1/study/sessions?limit=2&offset=0", headers=_auth_headers(token)
    )
    assert first_page.status_code == 200
    assert len(first_page.json()) == 2
    assert first_page.headers["X-Total-Count"] == "5"

    second_page = client.get(
        "/api/v1/study/sessions?limit=2&offset=2", headers=_auth_headers(token)
    )
    assert len(second_page.json()) == 2

    first_ids = {s["id"] for s in first_page.json()}
    second_ids = {s["id"] for s in second_page.json()}
    assert first_ids.isdisjoint(second_ids)


def test_list_sessions_default_pagination_returns_all_when_under_limit(client):
    token = _signup_and_get_token(client)
    client.post("/api/v1/study/sessions", json={"title": "세션"}, headers=_auth_headers(token))

    listing = client.get("/api/v1/study/sessions", headers=_auth_headers(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.headers["X-Total-Count"] == "1"


def test_session_requires_auth(client):
    response = client.get("/api/v1/study/sessions")
    assert response.status_code == 401


def test_send_message_persists_history_and_calls_ai(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "OS"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    send = client.post(
        f"/api/v1/study/sessions/{session_id}/messages",
        json={"content": "프로세스와 스레드 차이가 뭐야?"},
        headers=_auth_headers(token),
    )
    assert send.status_code == 200
    body = send.json()
    assert body["user_message"]["content"] == "프로세스와 스레드 차이가 뭐야?"
    assert "assistant reply to" in body["assistant_message"]["content"]

    detail = client.get(f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token))
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_other_user_cannot_access_session(client):
    token_a = _signup_and_get_token(client, email="a@example.com")
    token_b = _signup_and_get_token(client, email="b@example.com")

    create = client.post(
        "/api/v1/study/sessions", json={"title": "A의 세션"}, headers=_auth_headers(token_a)
    )
    session_id = create.json()["id"]

    response = client.get(f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token_b))
    assert response.status_code == 404


def test_delete_session(client):
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "삭제할 세션"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    delete = client.delete(f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token))
    assert delete.status_code == 204

    get_after_delete = client.get(
        f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token)
    )
    assert get_after_delete.status_code == 404


class GroundingFakeOllamaService:
    """chat()에 전달된 메시지를 기록해두고, 태그가 포함된 텍스트만 서로 가까운 벡터로 임베딩한다."""

    def __init__(self):
        self.last_messages = None

    async def chat(self, messages, model):
        self.last_messages = messages
        return "assistant reply"

    async def embed(self, text, model):
        if "기억할 사실" in text:
            return [1.0, 0.0]
        return [0.0, 1.0]


def test_first_message_has_no_grounding_when_corpus_is_empty(client):
    fake = GroundingFakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "그라운딩 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    client.post(
        f"/api/v1/study/sessions/{session_id}/messages",
        json={"content": "기억할 사실: 스레드는 프로세스 안에서 돈다"},
        headers=_auth_headers(token),
    )

    assert fake.last_messages is not None
    assert not any(m["role"] == "system" for m in fake.last_messages)


def test_later_message_is_grounded_with_relevant_legacy_content(client):
    fake = GroundingFakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "그라운딩 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    client.post(
        f"/api/v1/study/sessions/{session_id}/messages",
        json={"content": "기억할 사실: 스레드는 프로세스 안에서 돈다"},
        headers=_auth_headers(token),
    )

    client.post(
        f"/api/v1/study/sessions/{session_id}/messages",
        json={"content": "기억할 사실 관련해서 다시 설명해줘"},
        headers=_auth_headers(token),
    )

    system_messages = [m for m in fake.last_messages if m["role"] == "system"]
    assert len(system_messages) == 1
    assert "기억할 사실: 스레드는 프로세스 안에서 돈다" in system_messages[0]["content"]


def test_user_message_preserved_when_ai_call_fails(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "실패 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    send = client.post(
        f"/api/v1/study/sessions/{session_id}/messages",
        json={"content": "이 메시지는 저장돼야 한다"},
        headers=_auth_headers(token),
    )
    assert send.status_code == 500

    detail = client.get(f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token))
    messages = detail.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "이 메시지는 저장돼야 한다"


def test_stream_message_sends_deltas_then_done(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "스트리밍 세션"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as ws:
        ws.send_json({"content": "안녕?"})

        user_event = ws.receive_json()
        assert user_event["type"] == "user_message"
        assert user_event["data"]["content"] == "안녕?"

        delta_1 = ws.receive_json()
        delta_2 = ws.receive_json()
        assert delta_1 == {"type": "delta", "content": "안녕"}
        assert delta_2 == {"type": "delta", "content": "하세요"}

        done_event = ws.receive_json()
        assert done_event["type"] == "done"
        assert done_event["data"]["role"] == "assistant"
        assert done_event["data"]["content"] == "안녕하세요"

        # 테스트 클라이언트가 with 블록을 빠져나가며 서버 태스크를 강제 취소하면
        # (aiosqlite StaticPool을 쓰는 테스트 DB에서) 공유 커넥션이 깨질 수 있다 -
        # 명시적으로 정상 종료 이벤트를 먼저 보내 서버가 WebSocketDisconnect를
        # 정상적으로 받아 세션을 깔끔히 정리하게 한다.
        ws.close()

    detail = client.get(f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token))
    messages = detail.json()["messages"]
    assert len(messages) == 2
    assert messages[1]["content"] == "안녕하세요"


def test_stream_message_rejects_missing_token(client):
    from starlette.testclient import WebSocketDisconnect

    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "인증 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/v1/study/sessions/{session_id}/stream") as ws:
            ws.receive_json()


def test_stream_message_rejects_empty_content(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "빈 내용 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as ws:
        ws.send_json({"content": "   "})
        error_event = ws.receive_json()
        assert error_event["type"] == "error"


def test_stream_message_other_users_session_returns_error_event(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token_a = _signup_and_get_token(client, email="stream-a@example.com")
    token_b = _signup_and_get_token(client, email="stream-b@example.com")

    create = client.post(
        "/api/v1/study/sessions", json={"title": "A의 세션"}, headers=_auth_headers(token_a)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token_b}"
    ) as ws:
        ws.send_json({"content": "몰래 접근"})
        error_event = ws.receive_json()
        assert error_event["type"] == "error"


def test_stream_message_ai_failure_sends_error_event(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "실패 스트리밍"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as ws:
        ws.send_json({"content": "실패해라"})
        user_event = ws.receive_json()
        assert user_event["type"] == "user_message"
        error_event = ws.receive_json()
        assert error_event["type"] == "error"

    # AI 호출은 실패해도 사용자 메시지는 보존되어야 한다 (REST 버전과 동일한 보장).
    detail = client.get(f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token))
    messages = detail.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["content"] == "실패해라"
