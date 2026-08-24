import pytest

from app.core.config import get_settings
from app.core.dependencies import get_ollama_service
from app.services.ollama_service import OllamaServiceError
from app.services.study_service import _recent_history


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


def test_send_message_rejects_content_over_max_length(client, monkeypatch):
    monkeypatch.setenv("MAX_PROMPT_LENGTH", "5")
    get_settings.cache_clear()
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "길이 초과 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    response = client.post(
        f"/api/v1/study/sessions/{session_id}/messages",
        json={"content": "이 메시지는 5자보다 훨씬 깁니다"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_recent_history_treats_non_positive_limit_as_empty():
    """파이썬 슬라이싱에서 `history[-0:]`은 음수 0이 없어서 `history[0:]`, 즉
    전체 리스트가 되어버린다 - limit=0으로 "히스토리 없이 보내라"는 의도가
    조용히 "전체 히스토리를 다 보내라"로 뒤집히는 함정이다. 0과 음수를 둘 다
    빈 리스트로 명시 처리하는지, 그리고 양수일 때는 정말 뒤쪽 N개만 남기는지
    확인한다."""
    history = ["a", "b", "c", "d"]
    assert _recent_history(history, 0) == []
    assert _recent_history(history, -1) == []
    assert _recent_history(history, 2) == ["c", "d"]
    assert _recent_history(history, 100) == ["a", "b", "c", "d"]


class HistoryTrackingOllamaService:
    """chat()/chat_stream()에 실제로 전달된 메시지 목록을 그대로 기록해둔다.
    embed()는 항상 빈 벡터를 반환해 RAG 그라운딩이 절대 끼어들지 않게 해서,
    히스토리 길이 자체만 결정적으로 검증할 수 있게 한다."""

    def __init__(self):
        self.last_messages = None

    async def chat(self, messages, model):
        self.last_messages = messages
        return "assistant reply"

    async def chat_stream(self, messages, model):
        self.last_messages = messages
        yield "assistant reply"

    async def embed(self, text, model):
        return []


def test_send_message_truncates_history_to_configured_limit(client, monkeypatch):
    """send_message는 세션의 지금까지 전체 메시지 히스토리를 매번 그대로 다시
    프롬프트에 실어 Ollama에 보낸다 - 대화가 길어질수록 한 번의 호출에 드는
    토큰 수가 무한정 늘어나서, 언젠가 모델의 컨텍스트 윈도우를 넘기면 앞부분이
    조용히 잘리거나 응답 품질/지연이 나빠질 수 있다. MAX_CHAT_HISTORY_MESSAGES로
    가장 최근 메시지만 프롬프트에 포함되는지 확인한다."""
    monkeypatch.setenv("MAX_CHAT_HISTORY_MESSAGES", "2")
    get_settings.cache_clear()
    fake = HistoryTrackingOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "히스토리 제한 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    for i in range(3):
        response = client.post(
            f"/api/v1/study/sessions/{session_id}/messages",
            json={"content": f"메시지 {i}"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 200

    # 세 번째 호출 시점엔 이전 대화 4개(사용자 2 + 어시스턴트 2)가 이미 쌓여 있었다 -
    # MAX_CHAT_HISTORY_MESSAGES=2라 그중 최근 2개만 프롬프트에 포함되고, 거기에
    # 이번에 새로 보낸 메시지 1개가 더해져 총 3개여야 한다(전체 히스토리를 그대로
    # 실었다면 4 + 1 = 5개였을 것).
    assert len(fake.last_messages) == 3
    assert fake.last_messages[-1] == {"role": "user", "content": "메시지 2"}


def test_stream_message_truncates_history_to_configured_limit(client, monkeypatch):
    """위 REST 버전과 같은 확인을 stream_message(WebSocket)에도 반복한다 - 두
    경로가 같은 _recent_history() 헬퍼를 쓰지만 별도 코드 경로(제너레이터)라
    회귀가 한쪽에만 생길 수 있다."""
    monkeypatch.setenv("MAX_CHAT_HISTORY_MESSAGES", "2")
    get_settings.cache_clear()
    fake = HistoryTrackingOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "WS 히스토리 제한 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as ws:
        for i in range(3):
            ws.send_json({"content": f"메시지 {i}"})
            ws.receive_json()  # user_message
            ws.receive_json()  # delta
            ws.receive_json()  # done
        ws.close()

    assert len(fake.last_messages) == 3
    assert fake.last_messages[-1] == {"role": "user", "content": "메시지 2"}


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


def test_delete_session_404_for_nonexistent_session(client):
    token = _signup_and_get_token(client)
    response = client.delete(
        "/api/v1/study/sessions/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_send_message_404_for_nonexistent_session(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/study/sessions/00000000-0000-0000-0000-000000000000/messages",
        json={"content": "안녕"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_rename_session(client):
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "원래 제목"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    rename = client.patch(
        f"/api/v1/study/sessions/{session_id}",
        json={"title": "새 제목"},
        headers=_auth_headers(token),
    )
    assert rename.status_code == 200
    assert rename.json()["title"] == "새 제목"

    detail = client.get(f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token))
    assert detail.json()["title"] == "새 제목"


def test_rename_session_rejects_empty_title(client):
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "원래 제목"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/study/sessions/{session_id}", json={"title": ""}, headers=_auth_headers(token)
    )
    assert response.status_code == 422


def test_rename_session_404_for_nonexistent_session(client):
    token = _signup_and_get_token(client)
    response = client.patch(
        "/api/v1/study/sessions/00000000-0000-0000-0000-000000000000",
        json={"title": "새 제목"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_rename_session_404_for_other_users_session(client):
    token_a = _signup_and_get_token(client, email="rename-a@example.com")
    token_b = _signup_and_get_token(client, email="rename-b@example.com")
    create = client.post(
        "/api/v1/study/sessions", json={"title": "A의 세션"}, headers=_auth_headers(token_a)
    )
    session_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/study/sessions/{session_id}",
        json={"title": "가로채기 시도"},
        headers=_auth_headers(token_b),
    )
    assert response.status_code == 404


class GroundingFakeOllamaService:
    """chat()에 전달된 메시지를 기록해두고, 태그가 포함된 텍스트만 서로 가까운 벡터로 임베딩한다."""

    def __init__(self):
        self.last_messages = None

    async def chat(self, messages, model):
        self.last_messages = messages
        return "assistant reply"

    async def chat_stream(self, messages, model):
        self.last_messages = messages
        yield "assistant reply"

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


def test_stream_message_is_grounded_with_relevant_legacy_content(client):
    fake = GroundingFakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "스트리밍 그라운딩 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    client.post(
        f"/api/v1/study/sessions/{session_id}/messages",
        json={"content": "기억할 사실: 스레드는 프로세스 안에서 돈다"},
        headers=_auth_headers(token),
    )

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as ws:
        ws.send_json({"content": "기억할 사실 관련해서 다시 설명해줘"})
        ws.receive_json()  # user_message
        ws.receive_json()  # delta
        ws.receive_json()  # done
        ws.close()

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
    assert send.status_code == 502

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


def test_stream_websocket_closes_ollama_service_dependency_on_disconnect(client):
    """get_ollama_service는 요청/연결이 끝나면 finally에서 aclose()를 호출하는
    async generator 의존성이다 (httpx.AsyncClient 커넥션 정리 목적). 다른 WS
    테스트들은 dependency_overrides에 일반 함수(FakeOllamaService를 바로
    반환)를 꽂아 이 정리 로직 자체를 우회하므로, 실제 async generator
    형태로 오버라이드해 WebSocket 연결이 끊길 때도 FastAPI가 finally 블록을
    정상적으로 실행해주는지 별도로 검증한다."""
    closed = {"value": False}

    class TrackingOllamaService(FakeOllamaService):
        async def aclose(self):
            closed["value"] = True

    async def tracked_get_ollama_service():
        service = TrackingOllamaService()
        try:
            yield service
        finally:
            await service.aclose()

    client.app.dependency_overrides[get_ollama_service] = tracked_get_ollama_service
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "정리 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as ws:
        ws.send_json({"content": "안녕?"})
        ws.receive_json()  # user_message
        ws.receive_json()  # delta
        ws.receive_json()  # delta
        ws.receive_json()  # done
        ws.close()

    assert closed["value"] is True


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


def test_stream_message_rejects_malformed_token(client):
    from starlette.testclient import WebSocketDisconnect

    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "잘못된 토큰 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/api/v1/study/sessions/{session_id}/stream?token=not-a-real-jwt"
        ) as ws:
            ws.receive_json()


def test_stream_message_rejects_token_for_deleted_user(client):
    from starlette.testclient import WebSocketDisconnect

    signup = client.post(
        "/api/v1/auth/signup", json={"email": "ws-deleted@example.com", "password": "supersecret"}
    )
    token = signup.json()["access_token"]
    create = client.post(
        "/api/v1/study/sessions", json={"title": "탈퇴 계정 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    delete = client.request(
        "DELETE", "/api/v1/users/me", json={"current_password": "supersecret"}, headers=_auth_headers(token)
    )
    assert delete.status_code == 204

    # 계정이 삭제되면 세션도 함께 CASCADE로 지워지지만, access token 자체는 만료
    # 전까지 형식상 유효하다 - get_current_user_ws가 user_id로 사용자를 다시
    # 조회해 존재하지 않음을 확인하고 거부해야 한다.
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/api/v1/study/sessions/{session_id}/stream?token={token}"
        ) as ws:
            ws.receive_json()


def test_stream_message_closes_connection_after_idle_timeout(client, monkeypatch):
    """이 WebSocket 연결은 살아있는 동안 DB 커넥션 풀의 커넥션 하나와 Ollama
    클라이언트를 계속 붙잡고 있는다 - 클라이언트가 접속만 해두고 메시지를 하나도
    안 보내면 그 자원이 무한정 잠긴다(방치된 연결 몇 개만으로도 풀 전체가
    고갈될 수 있음). ws_idle_timeout_seconds를 짧게 줄여서, 아무것도 안 보내고
    기다리기만 해도 서버가 먼저 연결을 끊는지 확인한다."""
    from starlette.testclient import WebSocketDisconnect

    monkeypatch.setenv("WS_IDLE_TIMEOUT_SECONDS", "0.05")
    get_settings.cache_clear()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "유휴 타임아웃 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/api/v1/study/sessions/{session_id}/stream?token={token}"
        ) as ws:
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


def test_stream_message_rejects_content_over_max_length(client, monkeypatch):
    monkeypatch.setenv("MAX_PROMPT_LENGTH", "5")
    get_settings.cache_clear()
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "길이 초과 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as ws:
        ws.send_json({"content": "이 메시지는 5자보다 훨씬 깁니다"})
        error_event = ws.receive_json()
        assert error_event["type"] == "error"
        assert "최대 5자" in error_event["detail"]


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


def test_stream_message_rate_limited_after_exceeding_chat_rate_limit(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("CHAT_RATE_LIMIT", "1/minute")
    get_settings.cache_clear()

    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="stream-ratelimit@example.com")
    create = client.post(
        "/api/v1/study/sessions", json={"title": "레이트리밋 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as ws:
        ws.send_json({"content": "첫 메시지"})
        ws.receive_json()  # user_message
        ws.receive_json()  # delta
        ws.receive_json()  # delta
        ws.receive_json()  # done

        ws.send_json({"content": "두 번째 메시지"})
        error_event = ws.receive_json()
        assert error_event["type"] == "error"
        assert error_event["retry_after"] >= 0

        ws.close()

    # 레이트리밋에 걸린 두 번째 메시지는 세션에 저장되지 않았어야 한다.
    detail = client.get(f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token))
    messages = detail.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["content"] == "첫 메시지"
