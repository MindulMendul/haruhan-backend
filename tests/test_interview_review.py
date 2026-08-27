from datetime import timedelta

from app.core.clock import utcnow_naive
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


class CrashingOllamaService:
    """OllamaServiceError가 아닌, 라우트가 예상하지 못한 예외를 흉내낸다
    (예: 임베딩 응답 파싱 실패, DB 커넥션 끊김 등)."""

    async def chat_stream(self, messages, model):
        raise RuntimeError("boom")
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


def test_create_review_rejects_future_interview_date(client):
    """면접 복기는 이미 치른 면접을 되짚는 기능이라, 아직 안 일어난 미래 날짜는
    의미가 없다 - 스키마 검증에서 바로 422로 거부돼야 한다."""
    token = _signup_and_get_token(client, email="future-interview-date@example.com")
    tomorrow = (utcnow_naive().date() + timedelta(days=1)).isoformat()

    response = client.post(
        "/api/v1/interview/reviews",
        json=_create_payload(interview_date=tomorrow),
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_create_review_accepts_todays_interview_date(client):
    """오늘 치른 면접을 당일 바로 복기하는 것도 정상 케이스라, 오늘 날짜 자체는
    거부되면 안 된다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="today-interview-date@example.com")
    today = utcnow_naive().date().isoformat()

    response = client.post(
        "/api/v1/interview/reviews",
        json=_create_payload(interview_date=today),
        headers=_auth_headers(token),
    )
    assert response.status_code == 201


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


def test_list_all_for_user_breaks_created_at_ties_deterministically():
    """list_for_user()(페이지네이션 있음)는 위 테스트처럼 이미 id를 2차 정렬
    기준으로 쓰는데, 데이터 export가 쓰는 list_all_for_user()(페이지네이션
    없음, created_at 기준 정렬)는 같은 문제(SQL 표준상 동률 순서 미정의)가
    남아 있었다 - 페이지네이션이 없어 중복/누락 위험은 없지만, 같은 호출이
    매번 다른 순서를 반환할 수 있다는 점은 동일하다."""
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
    asyncio.run(repo.list_all_for_user(uuid.uuid4()))

    assert session.captured_statement is not None
    compiled = str(session.captured_statement)
    order_by_clause = compiled.split("ORDER BY")[1]
    assert "created_at" in order_by_clause
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


def test_update_review_rejects_future_interview_date(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="update-future-interview-date@example.com")

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]
    tomorrow = (utcnow_naive().date() + timedelta(days=1)).isoformat()

    update = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"interview_date": tomorrow},
        headers=_auth_headers(token),
    )
    assert update.status_code == 422


def test_update_review_with_explicit_null_interview_date_leaves_it_unchanged(client):
    """일부 클라이언트는 "안 바꾼 필드"도 null로 명시해서 보낼 수 있다 - 필드
    자체를 아예 안 보내는 것과 동작이 같아야 한다(둘 다 interview_date는
    그대로 유지). 검증기가 None을 미래 날짜로 오인해 거부하면 안 된다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="update-null-interview-date@example.com")

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]
    original_interview_date = create.json()["interview_date"]

    update = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"interview_date": None, "position": "프론트엔드 개발자"},
        headers=_auth_headers(token),
    )
    assert update.status_code == 200
    assert update.json()["interview_date"] == original_interview_date


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


def test_stream_create_review_rejects_when_at_max_concurrent_connections(client, monkeypatch):
    """학습챗 스트리밍과 마찬가지로 이 WebSocket 연결도 accept부터 종료까지
    DB 커넥션 풀의 커넥션 하나를 계속 점유한다 - 풀 크기보다 많은 동시 연결이
    열리면 풀 전체가 고갈될 수 있다. MAX_CONCURRENT_WS_CONNECTIONS를 1로
    줄여서, 이미 연결 하나가 열려 있는 동안 두 번째 연결 시도가 거부되는지
    확인한다."""
    import pytest
    from starlette.testclient import WebSocketDisconnect

    monkeypatch.setenv("MAX_CONCURRENT_WS_CONNECTIONS", "1")
    get_settings.cache_clear()
    token = _signup_and_get_token(client, email="stream-review-limit@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}"):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/interview/reviews/stream?token={token}"
            ) as second_ws:
                second_ws.receive_json()


def test_max_concurrent_ws_connections_is_shared_across_study_and_review_routes(client, monkeypatch):
    """학습챗 스트리밍과 면접복기 스트리밍은 별개 라우터지만 같은 DB 커넥션
    풀을 공유한다 - 두 라우트 중 하나에서 연결을 열었어도 합산된 동시 연결
    수가 상한에 걸리면 다른 라우트의 새 연결도 거부돼야 한다(라우트별로
    따로 세는 게 아니라 앱 전체에서 공유하는 카운터라는 게 이 기능의
    핵심이다)."""
    import pytest
    from starlette.testclient import WebSocketDisconnect

    monkeypatch.setenv("MAX_CONCURRENT_WS_CONNECTIONS", "1")
    get_settings.cache_clear()
    token = _signup_and_get_token(client, email="stream-review-shared-limit@example.com")

    study_create = client.post(
        "/api/v1/study/sessions", json={"title": "공유 상한 테스트"}, headers=_auth_headers(token)
    )
    study_session_id = study_create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{study_session_id}/stream?token={token}"
    ):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/interview/reviews/stream?token={token}"
            ) as review_ws:
                review_ws.receive_json()


def test_stream_create_review_rejects_invalid_payload(client):
    token = _signup_and_get_token(client, email="stream-review-invalid@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.send_json({"company": "하루한"})  # position/interview_date/content 누락
        error_event = ws.receive_json()
        assert error_event["type"] == "error"


def test_stream_create_review_validation_error_does_not_leak_raw_input_value(client, monkeypatch):
    """REST 쪽 422 응답(app.core.errors.validation_exception_handler)은 검증 실패
    필드의 원본 입력값이 devtools 히스토리/로깅 도구에 남을 수 있다는 이유로
    이미 제거하는데, 이 WS 경로는 FastAPI 자동 검증을 안 타고 model_validate()를
    직접 호출해서 str(ValidationError)를 그대로 detail로 보내면 그 sanitization을
    거치지 않는다 - 검증에 실패한 content 원문이 에러 메시지에 그대로 echo될 수
    있었다. 같은 헬퍼(sanitize_pydantic_errors)로 원본 값을 제거했는지 확인한다."""
    monkeypatch.setenv("MAX_REVIEW_CONTENT_LENGTH", "5")
    get_settings.cache_clear()
    token = _signup_and_get_token(client, email="stream-review-no-leak@example.com")

    # pydantic이 ValidationError 메시지의 input_value를 길면 가운데를 잘라 보여주므로
    # (예: 'SECRETMARKER98765가가...가가가가가가가'), 전체 문자열이 아니라 잘려도
    # 살아남는 맨 앞 마커로 확인해야 실제로 leak 여부를 가려낼 수 있다.
    marker = "SECRETMARKER98765"
    sensitive_content = marker + "가" * 60

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.send_json(_create_payload(content=sensitive_content))
        error_event = ws.receive_json()
        assert error_event["type"] == "error"
        assert marker not in error_event["detail"]


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


def test_stream_create_review_unexpected_exception_sends_error_event_and_logs(client, caplog):
    """OllamaServiceError가 아닌 예외는 main.py의 전역 unhandled_exception_handler로
    안 잡힌다 - 그 핸들러가 걸리는 Starlette ServerErrorMiddleware는 websocket
    scope를 그냥 통과시키기만 한다. 라우트가 직접 잡아서 에러 이벤트를 보내고
    로그도 남기는지 확인한다 (학습챗 스트리밍과 같은 패턴)."""
    import pytest
    from starlette.testclient import WebSocketDisconnect

    client.app.dependency_overrides[get_ollama_service] = lambda: CrashingOllamaService()
    token = _signup_and_get_token(client, email="stream-review-crash@example.com")

    with caplog.at_level("ERROR", logger="app.api.v1.routes.interview_review"):
        with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
            ws.send_json(_create_payload())
            error_event = ws.receive_json()
            assert error_event["type"] == "error"

            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()

    assert "처리되지 않은 예외" in caplog.text


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


def test_get_for_user_locked_requests_row_lock_on_postgres():
    """update_review()는 content가 바뀌면 피드백을 재생성하고 RAG 색인도 다시
    만드는 check-then-act다 - RagService.index_content()가 delete_for_source
    후 임베딩 호출을 거쳐 create하는 동안 커밋 없이 진행되는데, knowledge_chunks의
    source_id에는 유니크 제약이 없어서 같은 복기에 대한 거의 동시 수정(이중
    클릭, 네트워크 재시도)이 겹치면 중복 행(하나는 최신 content와 안 맞는 낡은
    내용)을 남길 수 있다. get_for_user_locked()가 실제로 FOR UPDATE를 요청하는
    쿼리를 만드는지, 세션에 전달되는 실제 statement를 가로채 확인한다(92번
    라운드의 QuizRepository.get_for_user_locked 테스트와 같은 패턴).

    SQLite는 FOR UPDATE 자체를 지원하지 않아 컴파일 시 조용히 빠져버리므로,
    이 잠금에 의존하는 동시성은 SQLite 기반 테스트 스위트로 재현/검증할 수
    없다 - 가로챈 statement를 실제로 잠그는 Postgres 방언으로 다시 컴파일해
    SQL 문자열에 "FOR UPDATE"가 포함되는지 확인하는 것으로 대신한다."""
    import asyncio
    import uuid

    from sqlalchemy.dialects import postgresql

    from app.repositories.interview_review_repository import InterviewReviewRepository

    class _CapturingResult:
        def scalar_one_or_none(self):
            return None

    class _CapturingSession:
        def __init__(self):
            self.captured_statement = None

        async def execute(self, statement):
            self.captured_statement = statement
            return _CapturingResult()

    session = _CapturingSession()
    repo = InterviewReviewRepository(session)
    asyncio.run(repo.get_for_user_locked(uuid.uuid4(), uuid.uuid4()))

    assert session.captured_statement is not None
    compiled = str(session.captured_statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in compiled
