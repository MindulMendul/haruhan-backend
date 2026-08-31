import pytest

from app.core.config import get_settings
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


class CrashingOllamaService:
    """OllamaServiceError가 아닌, 라우트가 예상하지 못한 예외를 흉내낸다
    (예: 임베딩 응답 파싱 실패, DB 커넥션 끊김 등)."""

    async def chat_stream(self, messages, model):
        raise RuntimeError("boom")
        yield ""  # pragma: no cover - async generator 문법상 필요 (도달 안 함)


def _signup_and_get_token(client, email="study@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "supersecret"}
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_session_returns_401_when_account_deleted_during_creation(db_session_factory, monkeypatch):
    """create_session()은 get_current_user 인증 확인과 이 INSERT 사이에(다른
    create류 메서드들과 달리 AI 호출 없이 곧바로 이어지지만) 다른 요청이
    UserService.delete_account()로 이 계정을 지워버리면(StudySession.user_id는
    nullable=False FK) IntegrityError로 실패할 수 있다 - 143~146라운드가 고친
    것과 같은 종류의 경쟁이다. StudySessionRepository.create가 실제 INSERT를
    하기 "직전" 별도 세션에서 이 계정을 완전히 지우도록 만들어서 이 좁은
    타이밍을 결정적으로 재현한다."""
    import asyncio

    from fastapi import HTTPException

    from app.repositories.study_session_repository import StudySessionRepository
    from app.repositories.user_repository import UserRepository
    from app.services.rag_service import RagService
    from app.services.study_service import StudyService

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()
            user_id = user.id

            class FakeOllamaService:
                async def chat(self, messages, model):
                    return "안 씀"

                async def chat_stream(self, messages, model):
                    yield "안 씀"

                async def embed(self, text, model):
                    return [1.0, 0.0, 0.0]

            ollama = FakeOllamaService()
            settings = get_settings()
            rag = RagService(session=session, ollama_service=ollama, settings=settings)
            service = StudyService(session=session, ollama_service=ollama, rag_service=rag, settings=settings)

            original_create = StudySessionRepository.create

            async def _deleting_create(self, user_id, title, model):
                async with db_session_factory() as session_b:
                    users_b = UserRepository(session_b)
                    target = await users_b.get_by_id(user_id)
                    await users_b.delete(target)
                    await session_b.commit()
                return await original_create(self, user_id, title, model)

            monkeypatch.setattr(StudySessionRepository, "create", _deleting_create)

            try:
                await service.create_session(user_id=user_id, title="세션", model="qwen2.5:3b")
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 401


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


def test_list_for_user_breaks_updated_at_ties_deterministically():
    """`ORDER BY updated_at DESC`만으로는 값이 같은 행(같은 순간에 만들어졌거나
    touch()된 세션들) 사이의 순서가 SQL 표준상 정의돼 있지 않다 - 페이지마다
    그 순서가 달라질 수 있어서, LIMIT/OFFSET으로 나눠 받으면 같은 세션이 두
    페이지에 다시 나오거나(중복) 어느 페이지에도 안 나올(누락) 수 있다.
    updated_at은 마이크로초 정밀도라 실제로 동률이 나기는 훨씬 드물지만
    (interview_review의 interview_date처럼 날짜 단위는 아님), 이 정렬
    로직 자체는 여전히 SQL 표준상 순서가 보장되지 않는 미정의 동작에
    기대고 있었다. 이 동시성은 SQLite 기반 테스트로 재현할 수 없어(68번
    라운드와 같은 성격의 한계), 리포지토리가 세션에 전달하는 statement를
    가로채 컴파일된 SQL의 ORDER BY 절에 updated_at뿐 아니라 id도 2차
    기준으로 포함돼 있는지 직접 확인한다."""
    import asyncio
    import uuid

    from app.repositories.study_session_repository import StudySessionRepository

    class _CapturingResult:
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
    repo = StudySessionRepository(session)
    asyncio.run(repo.list_for_user(uuid.uuid4(), limit=20, offset=0))

    assert session.captured_statement is not None
    order_by_clause = str(session.captured_statement).split("ORDER BY")[1]
    assert "updated_at" in order_by_clause
    assert "id" in order_by_clause


def test_list_all_for_user_breaks_created_at_ties_deterministically():
    """list_for_user()(페이지네이션 있음)는 위 테스트처럼 이미 id를 2차 정렬
    기준으로 쓰는데, 데이터 export가 쓰는 list_all_for_user()(페이지네이션
    없음)는 created_at만으로 정렬해 같은 문제(SQL 표준상 동률 순서 미정의)가
    남아 있었다 - 페이지네이션이 없어 중복/누락 위험은 없지만, 같은 호출이
    매번 다른 순서를 반환할 수 있다는 점은 동일하다."""
    import asyncio
    import uuid

    from app.repositories.study_session_repository import StudySessionRepository

    class _CapturingResult:
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
    repo = StudySessionRepository(session)
    asyncio.run(repo.list_all_for_user(uuid.uuid4()))

    assert session.captured_statement is not None
    order_by_clause = str(session.captured_statement).split("ORDER BY")[1]
    assert "created_at" in order_by_clause
    assert "id" in order_by_clause


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


def test_send_message_rejects_whitespace_only_content(client):
    """WS 스트리밍 경로(stream_message)는 공백만 있는 content를 이미
    "content는 비어 있을 수 없습니다"로 거부한다. REST 경로는 min_length=1만
    체크해 " " 같은 공백 문자열을 그대로 통과시켜, 빈 메시지가 저장되고
    불필요한 Ollama 호출까지 발생했다 - 두 경로가 동일한 규칙을 쓰도록
    맞춘다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "공백 메시지 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    response = client.post(
        f"/api/v1/study/sessions/{session_id}/messages",
        json={"content": "   "},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422

    detail = client.get(f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token))
    assert detail.json()["messages"] == []


def test_send_message_rejects_invisible_only_content(client):
    """`str.strip()`은 공백류만 제거하고 zero-width space(U+200B) 같은 유니코드
    Cf 카테고리 문자는 제거하지 못한다 - 이런 문자로만 이루어진 content가
    `not value.strip()` 검사를 통과해 저장되고 불필요한 Ollama 호출까지
    발생시켰다. is_blank()로 바꾼 뒤에도 공백-only 케이스와 동일하게
    거부되는지 확인한다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "보이지 않는 문자 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    response = client.post(
        f"/api/v1/study/sessions/{session_id}/messages",
        json={"content": "​​"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422

    detail = client.get(f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token))
    assert detail.json()["messages"] == []


def test_list_recent_for_session_returns_last_n_in_chronological_order(db_session_factory):
    """send_message/stream_message가 채팅 프롬프트에 넣을 최근 히스토리를
    구하던 이전 방식은 list_for_session()으로 세션 전체를 가져온 뒤 파이썬
    슬라이싱(`history[-limit:]`)으로 뒤쪽 N개만 남겼다 - 대화가 길어질수록
    (메시지 수 제한 없음) 매 턴마다 이미 안 쓸 앞부분까지 통째로 읽어오는
    낭비였다. list_recent_for_session()이 SQL `ORDER BY DESC LIMIT`으로
    필요한 만큼만 가져오면서도 순서/개수/경계값이 이전 파이썬 슬라이싱과
    동일하게 동작하는지 실제 DB 조회로 확인한다 - 특히 limit=0/음수를
    빈 리스트로 명시 처리하는지(파이썬의 `history[-0:]`이 빈 리스트가 아니라
    전체 리스트가 되어버리는 것과 같은 종류의 함정이 SQL `LIMIT`에도 있다).

    created_at은 server_default=func.now()라 짧은 시간에 여러 메시지를
    만들면 SQLite에서는(초 단위 정밀도) 값이 전부 같아지기 쉬워서, 실제로는
    id를 2차 정렬 기준으로 쓴다 - 하지만 id는 무작위 UUID라 순서 검증용으로는
    쓸 수 없다. 그래서 각 메시지의 created_at을 명시적으로 서로 다른 값으로
    지정해, 동률 없이 실제 시간순 정렬/자르기만 검증한다."""
    import asyncio
    import uuid
    from datetime import timedelta

    from app.core.clock import utcnow_naive
    from app.db.models.study_message import StudyMessage
    from app.repositories.study_message_repository import StudyMessageRepository
    from app.repositories.study_session_repository import StudySessionRepository
    from app.repositories.user_repository import UserRepository

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="히스토리 테스트", model="qwen2.5:3b"
            )
            await session.commit()

            base = utcnow_naive()
            for i in range(4):
                session.add(
                    StudyMessage(
                        id=uuid.uuid4(),
                        session_id=study_session.id,
                        role="user",
                        content=f"메시지 {i}",
                        created_at=base + timedelta(seconds=i),
                    )
                )
            await session.commit()

            messages = StudyMessageRepository(session)
            return (
                await messages.list_recent_for_session(study_session.id, 2),
                await messages.list_recent_for_session(study_session.id, 0),
                await messages.list_recent_for_session(study_session.id, -1),
                await messages.list_recent_for_session(study_session.id, 100),
            )

    last_two, zero_limit, negative_limit, over_limit = asyncio.run(_run())

    assert [m.content for m in last_two] == ["메시지 2", "메시지 3"]
    assert zero_limit == []
    assert negative_limit == []
    assert [m.content for m in over_limit] == [f"메시지 {i}" for i in range(4)]


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


def test_rename_session_returns_404_when_session_deleted_during_request(db_session_factory, monkeypatch):
    """rename_session()의 get_for_user() 조회는 잠금이 없어(get_for_user_locked()를
    쓰는 다른 메서드와 달리), 그 조회와 update_title()의 UPDATE 사이에 다른 요청이
    DELETE /study/sessions/{id}로 같은 세션을 지우면 UPDATE가 0행에 매치돼
    StaleDataError가 난다 - 184라운드가 고친 "계정 자체가 지워지는" 경쟁과는
    별개로, 계정은 멀쩡한 채 이 리소스만 지워지는 경우다. update_title()을
    몽키패치해 그 안에서 별도 세션으로 실제 삭제를 수행해 이 좁은 타이밍을
    결정적으로 재현한다."""
    import asyncio

    from fastapi import HTTPException

    from app.repositories.study_session_repository import StudySessionRepository
    from app.repositories.user_repository import UserRepository
    from app.services.rag_service import RagService
    from app.services.study_service import StudyService

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            sessions_repo = StudySessionRepository(session)
            study_session = await sessions_repo.create(user_id=user.id, title="세션", model="qwen2.5:3b")
            await session.commit()
            session_id = study_session.id

            ollama = FakeOllamaService()
            settings = get_settings()
            rag = RagService(session=session, ollama_service=ollama, settings=settings)
            service = StudyService(session=session, ollama_service=ollama, rag_service=rag, settings=settings)

            original_update_title = StudySessionRepository.update_title

            async def _deleting_update_title(self, target_session, title):
                async with db_session_factory() as session_b:
                    sessions_b = StudySessionRepository(session_b)
                    target = await sessions_b.get_for_user(session_id, user.id)
                    await sessions_b.delete(target)
                    await session_b.commit()
                return await original_update_title(self, target_session, title)

            monkeypatch.setattr(StudySessionRepository, "update_title", _deleting_update_title)

            try:
                await service.rename_session(session_id=session_id, user_id=user.id, title="새 제목")
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 404


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


def test_stream_message_logs_connect_and_disconnect_to_access_log(client, caplog):
    """AccessLogMiddleware(core/middleware.py)는 ASGI "http" scope만 다뤄서 이
    WebSocket 연결은 지금까지 구조화된 접근 로그(haruhan.access)에 전혀 남지
    않았다 - 이 라우트가 붙잡고 있는 DB 커넥션/Ollama 클라이언트를 누가 얼마나
    오래 점유했는지 grep 한 줄로 확인할 방법이 없었다. connect/disconnect가
    각각 한 줄씩 남는지, 클라이언트가 스스로 연결을 끊으면
    reason=client_disconnect로 남는지 확인한다."""
    import logging

    caplog.set_level(logging.INFO, logger="haruhan.access")
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "접근 로그 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(f"/api/v1/study/sessions/{session_id}/stream?token={token}"):
        pass

    records = [r.getMessage() for r in caplog.records if r.name == "haruhan.access"]
    connect_records = [m for m in records if m.startswith("ws_event=connect")]
    disconnect_records = [m for m in records if m.startswith("ws_event=disconnect")]
    assert len(connect_records) == 1
    assert f"path=/api/v1/study/sessions/{session_id}/stream" in connect_records[0]
    assert len(disconnect_records) == 1
    assert "duration_ms=" in disconnect_records[0]
    assert "reason=client_disconnect" in disconnect_records[0]


def test_stream_message_idle_timeout_logs_disconnect_reason(client, monkeypatch, caplog):
    """유휴 타임아웃으로 서버가 먼저 연결을 끊는 경우에도 disconnect 로그의
    reason이 client_disconnect가 아니라 idle_timeout으로 정확히 구분되는지
    확인한다 - 방치된 연결과 클라이언트가 스스로 끊은 연결을 로그만 보고
    구분할 수 있어야 운영 중 원인 파악에 의미가 있다."""
    import logging

    from starlette.testclient import WebSocketDisconnect

    monkeypatch.setenv("WS_IDLE_TIMEOUT_SECONDS", "0.05")
    get_settings.cache_clear()

    caplog.set_level(logging.INFO, logger="haruhan.access")
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "유휴 타임아웃 로그 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            f"/api/v1/study/sessions/{session_id}/stream?token={token}"
        ) as ws:
            ws.receive_json()

    records = [r.getMessage() for r in caplog.records if r.name == "haruhan.access"]
    disconnect_records = [m for m in records if m.startswith("ws_event=disconnect")]
    assert len(disconnect_records) == 1
    assert "reason=idle_timeout" in disconnect_records[0]


def test_stream_message_service_shutdown_disconnect_logs_distinct_reason(client, caplog):
    """uvicorn의 세 WebSocket 프로토콜 구현(websockets/wsproto 계열) 전부
    프로세스 종료(SIGTERM, 재배포 때마다 매번 일어남 - docker-compose.yml이
    워커 1개로 uvicorn을 그대로 돌림) 시 살아있는 연결에 code=1012("Service
    Restart")로 직접 종료를 건다 - 클라이언트가 스스로 끊은 게 아닌데도
    고치기 전엔 항상 "client_disconnect"로 남아, 재배포로 끊긴 연결과
    사용자가 실제로 끊은 연결을 로그만 보고 구분할 수 없었다(실제 uvicorn
    프로세스에 SIGTERM을 보내 직접 재현해 확인함). Starlette TestClient의
    WebSocket 세션이 `close(code=...)`로 보내는 값이 서버가 받는
    `WebSocketDisconnect.code`로 그대로 전달되므로, 실제 프로세스 없이도
    이 서버측 코드 경로 자체를 결정적으로 확인할 수 있다."""
    import logging

    caplog.set_level(logging.INFO, logger="haruhan.access")
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "서버 종료 로그 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(f"/api/v1/study/sessions/{session_id}/stream?token={token}") as ws:
        ws.close(code=1012)

    records = [r.getMessage() for r in caplog.records if r.name == "haruhan.access"]
    disconnect_records = [m for m in records if m.startswith("ws_event=disconnect")]
    assert len(disconnect_records) == 1
    assert "reason=server_shutdown" in disconnect_records[0]


def test_stream_message_rejects_when_at_max_concurrent_connections(client, monkeypatch):
    """WebSocket 연결 하나는 accept부터 종료까지 DB 커넥션 풀의 커넥션 하나를
    계속 점유한다(get_db가 연결 전체 수명 동안 열려 있는 FastAPI yield 의존성
    이라, 메시지 하나 처리할 때만 잠깐 빌리는 게 아님) - 풀 크기(기본
    pool_size=5 + max_overflow=5 = 10)보다 많은 동시 연결이 열리면 풀 전체가
    고갈돼 이 라우트뿐 아니라 앱의 다른 모든 요청까지 막힐 수 있다.
    MAX_CONCURRENT_WS_CONNECTIONS를 1로 줄여서, 이미 연결 하나가 열려 있는
    동안 두 번째 연결 시도가 accept 전에 거부되는지 확인한다."""
    from starlette.testclient import WebSocketDisconnect

    monkeypatch.setenv("MAX_CONCURRENT_WS_CONNECTIONS", "1")
    get_settings.cache_clear()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "동시 연결 제한 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(f"/api/v1/study/sessions/{session_id}/stream?token={token}"):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/study/sessions/{session_id}/stream?token={token}"
            ) as second_ws:
                second_ws.receive_json()


def test_stream_message_accepts_new_connection_after_previous_one_closes(client, monkeypatch):
    """연결이 끊기면(limit_ws_connections의 finally) 점유하던 슬롯이 반납돼,
    바로 다음 연결은 같은 상한 아래서도 정상적으로 받아들여져야 한다 - 카운터가
    증가만 하고 줄어들지 않는 회귀가 없는지 확인한다. 다른 WS 테스트들과 동일한
    패턴(메시지를 실제로 주고받고 명시적으로 ws.close())으로 첫 연결을 정상
    종료시킨 뒤 두 번째 연결을 연다."""
    monkeypatch.setenv("MAX_CONCURRENT_WS_CONNECTIONS", "1")
    get_settings.cache_clear()
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "슬롯 반납 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as first_ws:
        first_ws.send_json({"content": "첫 연결"})
        first_ws.receive_json()  # user_message
        first_ws.receive_json()  # delta
        first_ws.receive_json()  # delta
        first_ws.receive_json()  # done
        first_ws.close()

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as second_ws:
        second_ws.send_json({"content": "두 번째 연결"})
        user_event = second_ws.receive_json()
        assert user_event["type"] == "user_message"
        second_ws.receive_json()  # delta
        second_ws.receive_json()  # delta
        second_ws.receive_json()  # done
        second_ws.close()


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


def test_stream_message_rejects_invisible_only_content(client):
    """`str.strip()`은 공백류(`str.isspace()`가 True인 문자)만 제거하고,
    zero-width space(U+200B)처럼 화면엔 안 보이지만 공백이 아닌 유니코드 Cf
    카테고리 문자는 그대로 남긴다 - 그 결과 이런 문자로만 이루어진 content가
    `not content.strip()` 검사를 통과해버렸다. is_blank()로 바꾼 뒤에도 REST
    경로(test_send_message_rejects_whitespace_only_content)와 동일하게
    거부되는지 WS 경로에서도 확인한다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "보이지 않는 문자 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as ws:
        ws.send_json({"content": "​​"})
        error_event = ws.receive_json()
        assert error_event["type"] == "error"


def test_stream_message_rejects_malformed_json_frame(client):
    """websocket.receive_json()은 내부적으로 json.loads()를 그대로 호출하고
    예외를 잡지 않는다 - 이 라우트는 asyncio.TimeoutError만 잡고 있어서,
    깨진 JSON 프레임(느린 모바일 네트워크에서의 부분 전송, 클라이언트 버그
    등)이 오면 서버 쪽에서 처리되지 않은 JSONDecodeError가 그대로 터져
    연결이 비정상 종료됐다 - 다른 모든 잘못된 입력(빈 내용, 길이 초과 등)은
    {"type": "error"} 프레임으로 우아하게 처리하면서 이 경우만 예외로
    죽는 건 이 라우트 자신의 에러 처리 규약과 모순이다."""
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "깨진 JSON 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with client.websocket_connect(
        f"/api/v1/study/sessions/{session_id}/stream?token={token}"
    ) as ws:
        ws.send_text("이건 JSON이 아닙니다")
        error_event = ws.receive_json()
        assert error_event["type"] == "error"

        # 연결이 죽지 않고 계속 살아있는지, JSON이지만 객체가 아닌 페이로드로도
        # 확인한다 (payload.get("content")가 그대로면 AttributeError가 났을 것).
        ws.send_json([1, 2, 3])
        second_error = ws.receive_json()
        assert second_error["type"] == "error"


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


def test_stream_message_unexpected_exception_sends_error_event_and_logs(client, caplog):
    """OllamaServiceError가 아닌 예외(예: 임베딩/DB 계층에서 올라오는 예상 못 한
    예외)는 main.py의 전역 unhandled_exception_handler로 안 잡힌다 - 그 핸들러가
    걸리는 Starlette ServerErrorMiddleware는 websocket scope를 그냥 통과시키기만
    한다. 라우트가 직접 잡아서 에러 이벤트를 보내고 로그도 남기는지 확인한다."""
    from starlette.testclient import WebSocketDisconnect

    client.app.dependency_overrides[get_ollama_service] = lambda: CrashingOllamaService()
    token = _signup_and_get_token(client, email="stream-crash@example.com")
    create = client.post(
        "/api/v1/study/sessions", json={"title": "예상 못 한 예외"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    with caplog.at_level("ERROR", logger="app.api.v1.routes.study"):
        with client.websocket_connect(
            f"/api/v1/study/sessions/{session_id}/stream?token={token}"
        ) as ws:
            ws.send_json({"content": "터져라"})
            user_event = ws.receive_json()
            assert user_event["type"] == "user_message"
            error_event = ws.receive_json()
            assert error_event["type"] == "error"

            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()

    assert "처리되지 않은 예외" in caplog.text


def test_stream_message_disconnect_during_delta_send_logs_client_disconnect_not_error(
    client, caplog
):
    """스트리밍 도중(2번째 이후 send_json) 클라이언트가 실제로 사라지면
    Starlette의 WebSocket.send()가 전송 계층 OSError를 WebSocketDisconnect(1006)로
    바꿔 던진다 - 이 예외를 study.py가 `except WebSocketDisconnect: raise`로 먼저
    잡아 다시 던지지 않으면 그 아래 `except Exception:`이 이걸 "예상 못 한 서버
    오류"로 오분류해 이미 DISCONNECTED인 소켓에 에러 메시지를 다시 보내려다
    RuntimeError('Cannot call "send" once a close message has been sent.')로
    새어나간다(186라운드 픽스). 실제 WebSocket.send()의 상태 전이 로직을 그대로
    타도록 ASGI 전송 콜백(self._send)만 특정 시점에 OSError를 던지게 바꿔치기해
    재현한다 - send_json 자체를 가로채면 application_state가 실제로
    DISCONNECTED로 바뀌지 않아 버그가 재현되지 않는다."""
    import time as _time

    from starlette.websockets import WebSocket

    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()

    call_count = {"n": 0}
    original_send = WebSocket.send

    async def _flaky_send(self, message):
        call_count["n"] += 1
        # 1번째 send=accept, 2번째=user_message, 3번째=첫 delta("안녕") -
        # 스트리밍이 이미 시작된 뒤(user_message는 정상 도착) 그 다음 전송에서
        # 클라이언트가 사라지는 상황을 재현한다.
        if call_count["n"] == 3:
            original_transport_send = self._send

            async def _raise_oserror(msg):
                raise OSError("Broken pipe (simulated client disconnect)")

            self._send = _raise_oserror
            try:
                await original_send(self, message)
            finally:
                self._send = original_transport_send
        else:
            await original_send(self, message)

    import logging

    caplog.set_level(logging.INFO)

    monkeypatch_target = WebSocket.send
    WebSocket.send = _flaky_send
    try:
        token = _signup_and_get_token(client, email="stream-mid-disconnect@example.com")
        create = client.post(
            "/api/v1/study/sessions", json={"title": "중간 끊김"}, headers=_auth_headers(token)
        )
        session_id = create.json()["id"]

        with client.websocket_connect(
            f"/api/v1/study/sessions/{session_id}/stream?token={token}"
        ) as ws:
            ws.send_json({"content": "안녕"})
            user_event = ws.receive_json()
            assert user_event["type"] == "user_message"

            # 서버가 실제로 3번째 send(첫 delta)까지 진행할 시간을 준다 - 이
            # 시점 이후로는 서버가 더 이상 아무것도 보내지 않으므로(정상 처리
            # 시에도, 버그 상황에도) 여기서 다시 receive_json()을 부르면 영원히
            # 대기한다.
            deadline = _time.monotonic() + 20
            while call_count["n"] < 3 and _time.monotonic() < deadline:
                _time.sleep(0.02)
            assert call_count["n"] == 3, "서버가 3번째 send까지 도달하지 못했다"
    finally:
        WebSocket.send = monkeypatch_target

    assert "처리되지 않은 예외" not in caplog.text
    disconnect_records = [
        r.getMessage() for r in caplog.records if r.name == "haruhan.access"
    ]
    disconnect_records = [m for m in disconnect_records if m.startswith("ws_event=disconnect")]
    assert len(disconnect_records) == 1
    assert "reason=client_disconnect" in disconnect_records[0]


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
