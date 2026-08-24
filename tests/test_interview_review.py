from app.core.config import get_settings
from app.core.dependencies import get_ollama_service
from app.services.ollama_service import OllamaServiceError


class FakeOllamaService:
    def __init__(self):
        self.call_count = 0

    async def chat(self, messages, model):
        self.call_count += 1
        return f"feedback-{self.call_count}"

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]

    async def chat_stream(self, messages, model):
        self.call_count += 1
        for chunk in ["잘한", "점입니다"]:
            yield chunk


class FailingOllamaService:
    async def chat(self, messages, model):
        raise OllamaServiceError("boom")

    async def chat_stream(self, messages, model):
        raise OllamaServiceError("boom")
        yield ""  # pragma: no cover - async generator 문법상 필요 (도달 안 함)


def _signup_and_get_token(client, email="review@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "supersecret"}
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_payload(**overrides):
    payload = {
        "company": "하루한",
        "position": "백엔드 개발자",
        "interview_date": "2026-07-01",
        "content": "자기소개를 했고, 프로젝트 경험에 대해 질문받았습니다.",
    }
    payload.update(overrides)
    return payload


def test_create_review_generates_feedback(client):
    fake = FakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    assert create.status_code == 201
    body = create.json()
    assert body["ai_feedback"] == "feedback-1"
    assert body["company"] == "하루한"
    assert fake.call_count == 1


def test_create_review_ai_failure_returns_502(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    token = _signup_and_get_token(client)

    response = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    assert response.status_code == 502


def test_create_review_rejects_content_too_long(client, monkeypatch):
    monkeypatch.setenv("MAX_REVIEW_CONTENT_LENGTH", "5")
    get_settings.cache_clear()
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    response = client.post(
        "/api/v1/interview/reviews",
        json=_create_payload(content="이 내용은 5자보다 훨씬 깁니다"),
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_list_and_get_review(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]

    listing = client.get("/api/v1/interview/reviews", headers=_auth_headers(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    detail = client.get(f"/api/v1/interview/reviews/{review_id}", headers=_auth_headers(token))
    assert detail.status_code == 200
    assert detail.json()["id"] == review_id


def test_list_reviews_pagination(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    for i in range(5):
        client.post(
            "/api/v1/interview/reviews",
            json=_create_payload(company=f"회사{i}"),
            headers=_auth_headers(token),
        )

    first_page = client.get(
        "/api/v1/interview/reviews?limit=2&offset=0", headers=_auth_headers(token)
    )
    assert first_page.status_code == 200
    assert len(first_page.json()) == 2
    assert first_page.headers["X-Total-Count"] == "5"

    second_page = client.get(
        "/api/v1/interview/reviews?limit=2&offset=2", headers=_auth_headers(token)
    )
    assert len(second_page.json()) == 2

    first_ids = {r["id"] for r in first_page.json()}
    second_ids = {r["id"] for r in second_page.json()}
    assert first_ids.isdisjoint(second_ids)


def test_update_without_content_keeps_feedback(client):
    fake = FakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]
    assert fake.call_count == 1

    update = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"company": "다른회사"},
        headers=_auth_headers(token),
    )
    assert update.status_code == 200
    body = update.json()
    assert body["company"] == "다른회사"
    assert body["ai_feedback"] == "feedback-1"  # 재생성되지 않아야 함
    assert fake.call_count == 1


def test_update_with_same_content_does_not_regenerate(client):
    fake = FakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)
    payload = _create_payload()

    create = client.post("/api/v1/interview/reviews", json=payload, headers=_auth_headers(token))
    review_id = create.json()["id"]

    update = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"content": payload["content"]},
        headers=_auth_headers(token),
    )
    assert update.status_code == 200
    assert update.json()["ai_feedback"] == "feedback-1"
    assert fake.call_count == 1


def test_update_with_new_content_regenerates_feedback(client):
    fake = FakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]

    update = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"content": "완전히 다른 새 복기 내용입니다."},
        headers=_auth_headers(token),
    )
    assert update.status_code == 200
    body = update.json()
    assert body["content"] == "완전히 다른 새 복기 내용입니다."
    assert body["ai_feedback"] == "feedback-2"
    assert fake.call_count == 2


def test_update_position_only(client):
    fake = FakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]

    update = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"position": "프론트엔드 개발자"},
        headers=_auth_headers(token),
    )
    assert update.status_code == 200
    body = update.json()
    assert body["position"] == "프론트엔드 개발자"
    assert body["ai_feedback"] == "feedback-1"  # 재생성되지 않아야 함
    assert fake.call_count == 1


def test_update_interview_date_only(client):
    fake = FakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]

    update = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"interview_date": "2026-08-01"},
        headers=_auth_headers(token),
    )
    assert update.status_code == 200
    body = update.json()
    assert body["interview_date"] == "2026-08-01"
    assert fake.call_count == 1


def test_update_review_rejects_content_over_max_length(client, monkeypatch):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]

    # 생성은 기본 길이 제한으로 통과시켜두고, 수정 요청에서만 제한을 낮춰서
    # update_content_length 검증(생성 쪽과는 별개의 field_validator)이 걸리게 한다.
    monkeypatch.setenv("MAX_REVIEW_CONTENT_LENGTH", "5")
    get_settings.cache_clear()

    update = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"content": "이 내용은 5자보다 훨씬 깁니다"},
        headers=_auth_headers(token),
    )
    assert update.status_code == 422


def test_update_review_404_for_nonexistent_review(client):
    token = _signup_and_get_token(client)
    response = client.patch(
        "/api/v1/interview/reviews/00000000-0000-0000-0000-000000000000",
        json={"company": "새 회사"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_delete_review_404_for_nonexistent_review(client):
    token = _signup_and_get_token(client)
    response = client.delete(
        "/api/v1/interview/reviews/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_delete_review(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]

    delete = client.delete(f"/api/v1/interview/reviews/{review_id}", headers=_auth_headers(token))
    assert delete.status_code == 204

    get_after_delete = client.get(
        f"/api/v1/interview/reviews/{review_id}", headers=_auth_headers(token)
    )
    assert get_after_delete.status_code == 404


def test_other_user_cannot_access_review(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token_a = _signup_and_get_token(client, email="ra@example.com")
    token_b = _signup_and_get_token(client, email="rb@example.com")

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token_a)
    )
    review_id = create.json()["id"]

    response = client.get(f"/api/v1/interview/reviews/{review_id}", headers=_auth_headers(token_b))
    assert response.status_code == 404


def test_stream_create_review_sends_deltas_then_done(client):
    fake = FakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client, email="stream-review@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.send_json(_create_payload())

        delta_1 = ws.receive_json()
        delta_2 = ws.receive_json()
        assert delta_1 == {"type": "delta", "content": "잘한"}
        assert delta_2 == {"type": "delta", "content": "점입니다"}

        done_event = ws.receive_json()
        assert done_event["type"] == "done"
        assert done_event["data"]["ai_feedback"] == "잘한점입니다"
        assert done_event["data"]["company"] == "하루한"
        review_id = done_event["data"]["id"]

        ws.close()

    detail = client.get(f"/api/v1/interview/reviews/{review_id}", headers=_auth_headers(token))
    assert detail.status_code == 200
    assert detail.json()["ai_feedback"] == "잘한점입니다"


def test_stream_create_review_rejects_missing_token(client):
    import pytest
    from starlette.testclient import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/v1/interview/reviews/stream") as ws:
            ws.receive_json()


def test_stream_create_review_closes_connection_after_idle_timeout(client, monkeypatch):
    """이 WebSocket 연결도 학습챗 스트리밍과 마찬가지로 살아있는 동안 DB 커넥션
    풀의 커넥션 하나와 Ollama 클라이언트를 계속 붙잡고 있는다 - 클라이언트가
    접속만 해두고 메시지를 하나도 안 보내면 그 자원이 무한정 잠긴다.
    ws_idle_timeout_seconds를 짧게 줄여서, 아무것도 안 보내고 기다리기만 해도
    서버가 먼저 연결을 끊는지 확인한다."""
    import pytest
    from starlette.testclient import WebSocketDisconnect

    monkeypatch.setenv("WS_IDLE_TIMEOUT_SECONDS", "0.05")
    get_settings.cache_clear()
    token = _signup_and_get_token(client, email="stream-review-idle@example.com")

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
            ws.receive_json()


def test_stream_create_review_rejects_invalid_payload(client):
    token = _signup_and_get_token(client, email="stream-review-invalid@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.send_json({"company": "하루한"})  # position/interview_date/content 누락
        error_event = ws.receive_json()
        assert error_event["type"] == "error"


def test_stream_create_review_ai_failure_sends_error_event(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    token = _signup_and_get_token(client, email="stream-review-fail@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.send_json(_create_payload())
        error_event = ws.receive_json()
        assert error_event["type"] == "error"


def test_stream_create_review_rate_limited_after_exceeding_chat_rate_limit(client, monkeypatch):
    monkeypatch.setenv("CHAT_RATE_LIMIT", "1/minute")
    get_settings.cache_clear()

    fake = FakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client, email="stream-review-ratelimit@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.send_json(_create_payload())
        ws.receive_json()  # delta
        ws.receive_json()  # delta
        ws.receive_json()  # done

        ws.send_json(_create_payload(company="다른회사"))
        error_event = ws.receive_json()
        assert error_event["type"] == "error"
        assert error_event["retry_after"] >= 0

        ws.close()

    listing = client.get("/api/v1/interview/reviews", headers=_auth_headers(token))
    assert len(listing.json()) == 1
