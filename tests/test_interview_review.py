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


def test_list_for_user_breaks_interview_date_ties_deterministically():
    """interview_date는 하루 단위 정밀도의 사용자 입력값이라, 하루에 면접을 여러
    개 본 경우처럼 같은 날짜인 복기가 여러 개 있는 게 실제로 흔하다.
    `ORDER BY interview_date DESC`만으로는 값이 같은 행끼리의 순서가 SQL
    표준상 정의돼 있지 않다 - 페이지마다(혹은 같은 쿼리를 다시 실행할 때마다)
    그 순서가 달라질 수 있어서, `LIMIT/OFFSET`으로 나눠 받으면 같은 복기가
    두 페이지에 다시 나오거나(중복) 어느 페이지에도 안 나올(누락) 수 있다.

    바로 위 `test_list_reviews_pagination`이 정확히 이 동률 상황(고정된
    `_create_payload`의 interview_date로 복기 5개를 만듦)을 이미 재현하고
    있는데도 SQLite에서는 우연히 안정적인 순서를 돌려줘서 통과해버린다(직접
    확인함) - SQLite가 이 정도로 단순한 비동시성 시나리오에서 내부적으로
    일관된 순서를 우연히 돌려주기 때문이지, `id` 2차 정렬 기준이 있어서가
    아니다. 그래서 이 회귀는 SQLite 기반 테스트로 실제로 재현할 수 없다
    (68번 라운드에서 `SELECT ... FOR UPDATE`가 SQLite에서 조용히 빠지는
    것과 같은 성격의 한계) - 대신 리포지토리가 세션에 전달하는 실제 statement
    를 가로채, 컴파일된 SQL의 ORDER BY 절에 `interview_date`뿐 아니라 `id`도
    2차 기준으로 포함돼 있는지 직접 확인한다."""
    import asyncio
    import uuid

    from app.repositories.interview_review_repository import InterviewReviewRepository

    class _CapturingResult:
        def scalar_one_or_none(self):
            return None

        def scalars(self):
            return self

        def all(self):
            return []

    class _CapturingSession:
        def __init__(self):
            self.captured_statement = None

        async def execute(self, statement):
            self.captured_statement = statement
            return _CapturingResult()

    session = _CapturingSession()
    repo = InterviewReviewRepository(session)
    asyncio.run(repo.list_for_user(uuid.uuid4(), limit=20, offset=0))

    assert session.captured_statement is not None
    compiled = str(session.captured_statement)
    order_by_clause = compiled.split("ORDER BY")[1]
    assert "interview_date" in order_by_clause
    assert "id" in order_by_clause


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


def test_stream_create_review_rejects_malformed_json_frame(client):
    """websocket.receive_json()은 json.loads()를 그대로 호출하고 예외를 잡지
    않는다 - 이 라우트는 asyncio.TimeoutError만 잡고 있어서, 깨진 JSON
    프레임이 오면 처리되지 않은 JSONDecodeError가 그대로 터져 연결이
    비정상 종료됐다. study.py의 동일한 스트리밍 라우트와 같은 문제라
    같은 방식(잡아서 {"type": "error"} 프레임으로 응답 후 연결 유지)으로
    고쳤다."""
    token = _signup_and_get_token(client, email="stream-review-badjson@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.send_text("이건 JSON이 아닙니다")
        error_event = ws.receive_json()
        assert error_event["type"] == "error"

        # 연결이 죽지 않고 계속 살아있는지, 유효하지 않은 페이로드로 다시 확인한다.
        ws.send_json({"company": "하루한"})
        second_error = ws.receive_json()
        assert second_error["type"] == "error"


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
