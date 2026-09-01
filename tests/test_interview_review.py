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


class AlwaysBlankChatOllamaService:
    """chat()/chat_stream()이 매번 공백만 뱉는다 - OllamaService.chat()/
    chat_stream()은 Ollama가 200을 응답해도 본문에 message.content가 없거나
    명시적 null이면 OllamaServiceError를 던지지 않고 그냥 빈 문자열을(스트리밍
    버전은 아무 delta도) 돌려주는데, 재시도 없이 그대로 저장되면 ai_feedback이
    빈 문자열인 채로 커밋된다(test_interview_practice.py의
    AlwaysBlankChatOllamaService와 같은 패턴)."""

    def __init__(self):
        self.chat_call_count = 0
        self.chat_stream_call_count = 0

    async def chat(self, messages, model):
        self.chat_call_count += 1
        return "   "

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]

    async def chat_stream(self, messages, model):
        self.chat_stream_call_count += 1
        return
        yield ""  # pragma: no cover - async generator 문법상 필요 (도달 안 함)


class RecoversOnRetryOllamaService:
    """chat()/chat_stream() 첫 호출은 공백만 뱉고, 두 번째 호출부터는 정상
    응답을 준다(test_interview_practice.py의 RecoversOnRetryOllamaService와
    같은 패턴)."""

    def __init__(self):
        self.chat_call_count = 0
        self.chat_stream_call_count = 0

    async def chat(self, messages, model):
        self.chat_call_count += 1
        if self.chat_call_count == 1:
            return "   "
        return f"feedback-{self.chat_call_count}"

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]

    async def chat_stream(self, messages, model):
        self.chat_stream_call_count += 1
        if self.chat_stream_call_count == 1:
            return
        for chunk in ["잘한", "점입니다"]:
            yield chunk


class WhitespaceDeltaLeakOllamaService:
    """chat_stream()이 공백뿐인 조각(" ")을 하나 yield하고 끝난다 -
    test_study.py의 같은 클래스와 같은 이유(그쪽 docstring 참고)로, 이
    조각은 이미 stream_create_review()가 "delta" 이벤트로 클라이언트에
    전송한 뒤라 조용히 재시도하면 안 된다."""

    def __init__(self):
        self.chat_stream_call_count = 0

    async def chat(self, messages, model):
        return "unused"

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]

    async def chat_stream(self, messages, model):
        self.chat_stream_call_count += 1
        yield " "


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
    의미가 없다 - 스키마 검증에서 바로 422로 거부돼야 한다. 164라운드가 KST
    등 UTC보다 앞선 시간대와의 어긋남을 흡수하려고 하루의 여유를 뒀으므로,
    그 여유를 넘어서는(2일 뒤) 명백한 미래 날짜로 확인한다."""
    token = _signup_and_get_token(client, email="future-interview-date@example.com")
    clearly_future = (utcnow_naive().date() + timedelta(days=2)).isoformat()

    response = client.post(
        "/api/v1/interview/reviews",
        json=_create_payload(interview_date=clearly_future),
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_create_review_accepts_tomorrows_interview_date_as_timezone_grace(client):
    """interview_date는 tz 정보 없는 순수 날짜라 사용자의 로컬 달력 기준
    "오늘"을 뜻하는데, 서버는 utcnow_naive()로 UTC 기준 "오늘"만 안다 - 이
    앱은 한국어 UI로 KST(UTC+9)를 주 대상으로 하므로, UTC 자정 전(KST로는
    이미 다음날 오전)에 정당한 "오늘" 날짜를 보내면 서버 UTC 기준 "내일"과
    같은 값이 된다. 이 시간대 어긋남을 흡수하도록 하루의 여유를 뒀는지
    확인한다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="tz-grace-interview-date@example.com")
    utc_tomorrow = (utcnow_naive().date() + timedelta(days=1)).isoformat()

    response = client.post(
        "/api/v1/interview/reviews",
        json=_create_payload(interview_date=utc_tomorrow),
        headers=_auth_headers(token),
    )
    assert response.status_code == 201


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


def test_create_review_returns_502_when_feedback_is_blank(client):
    """공백뿐인 AI 피드백이 그대로 ai_feedback으로 저장되지 않고, 재시도(2회)까지
    소진한 뒤 502로 실패 처리되는지 확인한다 - 이 기능의 핵심인 ai_feedback이
    빈 문자열로 영구히 남으면 재생성할 방법이 없다(update_review는 content가
    실제로 바뀔 때만 다시 생성함)."""
    fake = AlwaysBlankChatOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client, email="blank-feedback@example.com")

    response = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    assert response.status_code == 502
    assert fake.chat_call_count == 2


def test_create_review_recovers_when_first_feedback_is_blank(client):
    """AI 피드백 재시도가 실제로 성공을 복구하는지(무조건 실패 처리하는 게
    아니라) 확인한다 - 첫 시도는 공백, 두 번째 시도는 정상 응답."""
    fake = RecoversOnRetryOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client, email="recovers-feedback@example.com")

    response = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    assert response.status_code == 201
    assert fake.chat_call_count == 2
    assert response.json()["ai_feedback"] == "feedback-2"


def test_update_review_returns_502_when_feedback_is_blank(client):
    """content를 실제로 바꿔 피드백을 재생성하는 update_review 경로도 REST
    create_review와 같은 보호를 받는지 확인한다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="update-blank-feedback@example.com")
    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]

    fake = AlwaysBlankChatOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    response = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"content": "완전히 다른 내용으로 바꿉니다"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 502
    assert fake.chat_call_count == 2

    # 원래 내용/피드백이 실패한 재생성으로 훼손되지 않고 그대로 남아 있어야 한다.
    detail = client.get(f"/api/v1/interview/reviews/{review_id}", headers=_auth_headers(token))
    assert detail.json()["content"] == _create_payload()["content"]


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


def test_create_review_rejects_whitespace_only_content(client):
    """min_length=1은 빈 문자열만 막을 뿐 공백만 있는 값은 통과시킨다 - 통과하면
    빈 내용으로 AI 피드백을 생성해 저장한다. 121/122라운드가 범위 밖으로
    미뤄뒀던 필드다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    response = client.post(
        "/api/v1/interview/reviews",
        json=_create_payload(content="   "),
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_update_review_rejects_whitespace_only_content(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"content": "   "},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_create_review_rejects_invisible_only_content(client):
    """`str.strip()`은 공백류만 제거하고 zero-width space(U+200B) 같은 유니코드
    Cf 카테고리 문자는 제거하지 못한다 - 이런 문자로만 이루어진 content가
    공백-only 검사를 통과해버렸다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    response = client.post(
        "/api/v1/interview/reviews",
        json=_create_payload(content="​​"),
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_update_review_rejects_invisible_only_content(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"content": "​​"},
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
    """164라운드가 KST 등 시간대 어긋남을 흡수하려고 하루의 여유를 뒀으므로,
    그 여유를 넘어서는(2일 뒤) 명백한 미래 날짜로 확인한다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="update-future-interview-date@example.com")

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]
    clearly_future = (utcnow_naive().date() + timedelta(days=2)).isoformat()

    update = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"interview_date": clearly_future},
        headers=_auth_headers(token),
    )
    assert update.status_code == 422


def test_update_review_accepts_tomorrows_interview_date_as_timezone_grace(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="update-tz-grace-interview-date@example.com")

    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]
    utc_tomorrow = (utcnow_naive().date() + timedelta(days=1)).isoformat()

    update = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"interview_date": utc_tomorrow},
        headers=_auth_headers(token),
    )
    assert update.status_code == 200


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


def test_update_review_skips_row_lock_when_content_is_not_being_changed(client, monkeypatch):
    """update_review()의 FOR UPDATE 잠금(get_for_user_locked)은 "content가
    실제로 바뀌었는지" 판단(get_for_user_locked() docstring 참고)을 보호하기
    위한 것뿐이다 - content를 아예 안 보내는 요청(company/position/
    interview_date만 바꾸는 흔한 PATCH)은 그 판단 자체가 항상 False로 고정돼
    있어 잠글 이유가 없다. 그런데도 무조건 잠그면, 이 흔한 "메타데이터만
    수정" 요청이 같은 복기에 대한 다른 요청의 AI 재생성 호출(최대 몇 분
    걸릴 수 있음, update_review()의 content_changed 분기 주석 참고) 뒤에서
    그 호출이 끝날 때까지 아무 이유 없이 대기하게 된다. content가 요청에
    없으면 잠금 없는 get_for_user()를, 있으면 잠금 있는 get_for_user_
    locked()를 쓰는지 - 실제 Postgres 잠금 없이도 - 저장소 메서드 호출
    자체로 직접 확인한다."""
    from app.repositories.interview_review_repository import InterviewReviewRepository

    locked_calls: list[int] = []
    unlocked_calls: list[int] = []
    original_locked = InterviewReviewRepository.get_for_user_locked
    original_unlocked = InterviewReviewRepository.get_for_user

    async def _tracking_locked(self, *args, **kwargs):
        locked_calls.append(1)
        return await original_locked(self, *args, **kwargs)

    async def _tracking_unlocked(self, *args, **kwargs):
        unlocked_calls.append(1)
        return await original_unlocked(self, *args, **kwargs)

    monkeypatch.setattr(InterviewReviewRepository, "get_for_user_locked", _tracking_locked)
    monkeypatch.setattr(InterviewReviewRepository, "get_for_user", _tracking_unlocked)

    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="update-lock-skip@example.com")
    create = client.post(
        "/api/v1/interview/reviews", json=_create_payload(), headers=_auth_headers(token)
    )
    review_id = create.json()["id"]

    locked_calls.clear()
    unlocked_calls.clear()

    metadata_only = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"company": "새 회사"},
        headers=_auth_headers(token),
    )
    assert metadata_only.status_code == 200
    assert unlocked_calls == [1]
    assert locked_calls == []

    locked_calls.clear()
    unlocked_calls.clear()

    content_change = client.patch(
        f"/api/v1/interview/reviews/{review_id}",
        json={"content": "완전히 다른 내용으로 바꿉니다"},
        headers=_auth_headers(token),
    )
    assert content_change.status_code == 200
    assert locked_calls == [1]
    assert unlocked_calls == []


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


def test_stream_create_review_rejects_further_messages_after_token_expires_mid_connection(client):
    """study.py의 stream_message와 같은 이유(그쪽 테스트 docstring 참고)로,
    get_current_user_ws()는 accept() 전 딱 한 번만 토큰을 검증한다 - 그
    뒤로는 REST와 달리 connect 시점엔 유효했던 토큰이 그 사이 만료돼도
    계속 인증된 것처럼 메시지를 처리했다. 1초 뒤 만료되는 토큰으로 연결한
    뒤 만료를 기다리고, 그 다음 메시지를 보내면 정상 처리되지 않고 연결이
    거부되는지 확인한다."""
    import time as _time

    import jwt as pyjwt
    import pytest
    from starlette.testclient import WebSocketDisconnect

    from app.core.tokens import ACCESS_TOKEN_TYPE, decode_access_token

    token = _signup_and_get_token(client, email="stream-review-expiring-token@example.com")

    settings = get_settings()
    user_id = decode_access_token(token, settings)["sub"]
    now_ts = int(_time.time())
    # WS 핸드셰이크(get_current_user_ws의 토큰 검증)가 끝나기 전에 만료되면
    # 연결 자체가 거부돼(이 테스트가 확인하려는 "연결 도중 만료"와는 다른
    # 상황) __enter__에서 바로 실패해버린다 - 전체 스위트처럼 스레드가 많을
    # 때는 핸드셰이크 자체가 지연될 수 있어 넉넉한 여유를 둔다.
    short_lived_token = pyjwt.encode(
        {"sub": user_id, "type": ACCESS_TOKEN_TYPE, "iat": now_ts, "exp": now_ts + 5},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with client.websocket_connect(
        f"/api/v1/interview/reviews/stream?token={short_lived_token}"
    ) as ws:
        _time.sleep(5.5)

        # 통제 확인: 같은(이제 만료된) 토큰으로 REST 호출은 이미 401을 낸다.
        me = client.get("/api/v1/users/me", headers=_auth_headers(short_lived_token))
        assert me.status_code == 401

        ws.send_json(_create_payload())
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_stream_create_review_logs_connect_and_disconnect_to_access_log(client, caplog):
    """AccessLogMiddleware(core/middleware.py)는 ASGI "http" scope만 다뤄서 이
    WebSocket 연결은 지금까지 구조화된 접근 로그(haruhan.access)에 전혀 남지
    않았다 - 이 라우트가 붙잡고 있는 DB 커넥션/Ollama 클라이언트를 누가 얼마나
    오래 점유했는지 grep 한 줄로 확인할 방법이 없었다. connect/disconnect가
    각각 한 줄씩 남는지, 클라이언트가 스스로 연결을 끊으면
    reason=client_disconnect로 남는지 확인한다."""
    import logging

    caplog.set_level(logging.INFO, logger="haruhan.access")
    token = _signup_and_get_token(client, email="stream-review-access-log@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}"):
        pass

    records = [r.getMessage() for r in caplog.records if r.name == "haruhan.access"]
    connect_records = [m for m in records if m.startswith("ws_event=connect")]
    disconnect_records = [m for m in records if m.startswith("ws_event=disconnect")]
    assert len(connect_records) == 1
    assert "path=/api/v1/interview/reviews/stream" in connect_records[0]
    assert len(disconnect_records) == 1
    assert "duration_ms=" in disconnect_records[0]
    assert "reason=client_disconnect" in disconnect_records[0]


def test_stream_create_review_idle_timeout_logs_disconnect_reason(client, monkeypatch, caplog):
    """유휴 타임아웃으로 서버가 먼저 연결을 끊는 경우에도 disconnect 로그의
    reason이 client_disconnect가 아니라 idle_timeout으로 정확히 구분되는지
    확인한다 - 방치된 연결과 클라이언트가 스스로 끊은 연결을 로그만 보고
    구분할 수 있어야 운영 중 원인 파악에 의미가 있다."""
    import logging

    import pytest
    from starlette.testclient import WebSocketDisconnect

    monkeypatch.setenv("WS_IDLE_TIMEOUT_SECONDS", "0.05")
    get_settings.cache_clear()

    caplog.set_level(logging.INFO, logger="haruhan.access")
    token = _signup_and_get_token(client, email="stream-review-idle-log@example.com")

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
            ws.receive_json()

    records = [r.getMessage() for r in caplog.records if r.name == "haruhan.access"]
    disconnect_records = [m for m in records if m.startswith("ws_event=disconnect")]
    assert len(disconnect_records) == 1
    assert "reason=idle_timeout" in disconnect_records[0]


def test_stream_create_review_service_shutdown_disconnect_logs_distinct_reason(client, caplog):
    """uvicorn의 세 WebSocket 프로토콜 구현 전부 프로세스 종료(SIGTERM, 재배포
    때마다 매번 일어남) 시 살아있는 연결에 code=1012("Service Restart")로
    직접 종료를 건다 - study.py의 stream_message와 같은 이유(그쪽 테스트
    docstring 참고, 실제 uvicorn 프로세스로 직접 재현해 확인함)로 이 경우도
    "client_disconnect"가 아니라 구분되는 reason으로 남아야 한다."""
    import logging

    caplog.set_level(logging.INFO, logger="haruhan.access")
    token = _signup_and_get_token(client, email="stream-review-shutdown-log@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.close(code=1012)

    records = [r.getMessage() for r in caplog.records if r.name == "haruhan.access"]
    disconnect_records = [m for m in records if m.startswith("ws_event=disconnect")]
    assert len(disconnect_records) == 1
    assert "reason=server_shutdown" in disconnect_records[0]


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


def test_stream_create_review_rejects_binary_frame(client):
    """203라운드: websocket.receive_json()은 기본(mode="text")으로
    message["text"]에 바로 접근한다(starlette/websockets.py) - 클라이언트가
    텍스트 대신 바이너리 프레임을 보내면 ASGI 메시지에 "text" 키가 없어(대신
    "bytes"만 있음) json.loads()까지 가기도 전에 KeyError('text')가 그대로
    새어나갔다. study.py의 동일한 문제와 같은 방식으로 고쳤다 - 연결이 죽지
    않고 에러 이벤트를 받은 뒤에도 정상 메시지를 계속 처리할 수 있는지
    확인한다."""
    fake = FakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client, email="stream-review-binary@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.send_bytes(b"\x00\x01\x02binary-frame-not-text")
        error_event = ws.receive_json()
        assert error_event["type"] == "error"

        ws.send_json(_create_payload())
        while True:
            event = ws.receive_json()
            if event["type"] == "done":
                break


def test_stream_create_review_sends_error_event_when_feedback_is_blank(client):
    """REST 버전(test_create_review_returns_502_when_feedback_is_blank)과 같은
    확인을 스트리밍(WebSocket) 경로에도 반복한다 - chat_stream()은 content가
    있는 조각만 yield하므로, 재시도 없이 그대로 끝나면 아무 delta도 못 보낸
    채 ai_feedback이 빈 문자열로 커밋된다."""
    fake = AlwaysBlankChatOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client, email="stream-blank-feedback@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.send_json(_create_payload())
        error_event = ws.receive_json()
        assert error_event["type"] == "error"

    assert fake.chat_stream_call_count == 2


def test_stream_create_review_recovers_when_first_feedback_is_blank(client):
    """스트리밍 경로에서도 재시도가 실제로 성공을 복구하는지 확인한다 - 첫
    시도는 delta를 하나도 못 보내고 끝나고, 두 번째 시도부터 정상적으로
    delta가 오는지."""
    fake = RecoversOnRetryOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client, email="stream-recovers-feedback@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.send_json(_create_payload())

        # done을 만날 때까지 읽는다(delta 개수를 미리 고정하지 않는다) - 만약
        # 재시도가 없다면(회귀) 실패한 첫 시도가 delta 없이 곧장 done으로
        # 끝나버리는데, 그 경우에도 여기서 자연스럽게 멈춘다. delta 슬롯
        # 수를 미리 고정해 두면 그 회귀 상황에서 다음 receive_json()이 영원히
        # 오지 않을 메시지를 기다리며 테스트가 멈춰버린다.
        deltas = []
        while True:
            event = ws.receive_json()
            if event["type"] == "done":
                break
            assert event["type"] == "delta"
            deltas.append(event["content"])

    assert deltas == ["잘한", "점입니다"]
    assert fake.chat_stream_call_count == 2


def test_stream_create_review_fails_instead_of_retrying_when_leaked_whitespace_delta_already_sent(
    client,
):
    """study.py의 같은 픽스와 같은 이유(그쪽 테스트 docstring 참고)로,
    공백뿐인 조각이라도 이미 "delta" 이벤트로 클라이언트에 전송된 뒤라면
    조용히 재시도해선 안 된다 - 재시도 대신 곧바로 error 이벤트로 실패
    처리되고, chat_stream이 딱 한 번만 호출되는지(=재시도가 실제로 일어나지
    않는지) 확인한다."""
    fake = WhitespaceDeltaLeakOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client, email="stream-review-whitespace-leak@example.com")

    with client.websocket_connect(f"/api/v1/interview/reviews/stream?token={token}") as ws:
        ws.send_json(_create_payload())

        events = []
        while True:
            event = ws.receive_json()
            events.append(event)
            if event["type"] in ("done", "error"):
                break

    assert events[-1]["type"] == "error"
    assert not any(e["type"] == "done" for e in events)
    assert fake.chat_stream_call_count == 1


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


def test_stream_create_review_disconnect_during_delta_send_logs_client_disconnect_not_error(
    client, caplog
):
    """study.py의 stream_message와 같은 이유(그쪽 테스트 docstring 참고)로,
    스트리밍 도중 클라이언트가 실제로 사라지면 Starlette의 WebSocket.send()가
    전송 계층 OSError를 WebSocketDisconnect(1006)로 바꿔 던진다 - 이 라우트가
    `except WebSocketDisconnect: raise`로 먼저 잡아 다시 던지지 않으면 아래
    `except Exception:`이 이미 DISCONNECTED인 소켓에 에러 메시지를 다시
    보내려다 RuntimeError로 새어나간다(186라운드 픽스). ASGI 전송 콜백
    (self._send)만 특정 시점에 OSError를 던지게 바꿔치기해 WebSocket.send()의
    실제 상태 전이 로직을 그대로 타면서 재현한다."""
    import logging
    import threading
    import weakref

    from starlette.websockets import WebSocket

    fake = FakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake

    # 전체 스위트에서 이 테스트가 드물게(간헐적으로) 실패하는 걸 발견했다 -
    # WebSocket.send를 클래스 레벨로 바꿔치기하기 때문에, 다른 테스트가 남긴
    # 아직 완전히 정리되지 않은 WebSocket 인스턴스(다른 백그라운드 anyio
    # 포털 스레드에서 실행 중)가 있으면 그쪽의 send 호출까지 전역
    # call_count를 함께 증가시켜, "3번째 호출 = 이 테스트의 두 번째 delta"라는
    # 전제가 깨질 수 있다. WeakKeyDictionary로 인스턴스(self)별로 호출
    # 횟수를 따로 세어, 다른 연결의 트래픽과 절대 섞이지 않게 한다.
    per_instance_counts: "weakref.WeakKeyDictionary[WebSocket, int]" = weakref.WeakKeyDictionary()
    original_send = WebSocket.send

    async def _flaky_send(self, message):
        n = per_instance_counts.get(self, 0) + 1
        per_instance_counts[self] = n
        # 1번째 send=accept, 2번째=첫 delta("잘한"), 3번째=두 번째
        # delta("점입니다") - 스트리밍이 이미 시작된 뒤(첫 delta는 정상 도착)
        # 그 다음 전송에서 클라이언트가 사라지는 상황을 재현한다.
        if n == 3:
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

    caplog.set_level(logging.INFO)

    # caplog.records를 폴링하는 대신 access_logger.info() 자체를 감싸 disconnect
    # 로그가 실제로 기록되는 순간 threading.Event를 직접 세운다 - 폴링 주기
    # 슬랙이나 caplog 내부 타이밍에 기대지 않는, 경합 없는 신호다. 처음엔
    # 실제 로거 호출이 끝난 뒤 Event를 세우고 그 뒤 caplog.records에서
    # 다시 찾는 방식이었는데, 그렇게 해도 전체 스위트 안에서 아주 드물게
    # (Event는 세워졌는데 caplog.records엔 아직 없는 상태로) 실패하는 걸
    # 다시 관찰했다(study.py의 같은 테스트에서 먼저 발견) - pytest의
    # LogCaptureHandler 자체가 스레드 간에 정확히 언제 가시성이 보장되는지
    # 까지는 신뢰하지 않기로 하고, 이 콜백 안에서 메시지를 직접 캡처해
    # (caplog와는 별개의, 이 테스트만의 로컬 리스트) 그 값 자체로 확인한다
    # - caplog의 내부 타이밍에 아예 의존하지 않는다.
    access_logger = logging.getLogger("haruhan.access")
    disconnect_logged = threading.Event()
    disconnect_messages: list[str] = []
    original_access_info = access_logger.info

    def _tracking_info(msg, *args, **kwargs):
        result = original_access_info(msg, *args, **kwargs)
        if isinstance(msg, str) and msg.startswith("ws_event=disconnect"):
            disconnect_messages.append(msg % args if args else msg)
            disconnect_logged.set()
        return result

    access_logger.info = _tracking_info

    monkeypatch_target = WebSocket.send
    WebSocket.send = _flaky_send
    try:
        token = _signup_and_get_token(client, email="stream-review-mid-disconnect@example.com")

        with client.websocket_connect(
            f"/api/v1/interview/reviews/stream?token={token}"
        ) as ws:
            ws.send_json(_create_payload())
            first_delta = ws.receive_json()
            assert first_delta == {"type": "delta", "content": "잘한"}

            # 서버가 실제로 3번째 send(두 번째 delta)에서 OSError를 만나
            # disconnect 처리(finally 블록의 접근 로그 기록까지)를 완전히
            # 마칠 때까지 기다린다 - 이후로는 서버가 더 이상 아무것도 보내지
            # 않으므로(정상 처리 시에도, 버그 상황에도) 여기서 receive_json()을
            # 부르면 영원히 대기한다.
            fired = disconnect_logged.wait(timeout=20)
            assert fired, "disconnect 접근 로그가 제시간에 기록되지 않았다"
    finally:
        WebSocket.send = monkeypatch_target
        access_logger.info = original_access_info

    assert "처리되지 않은 예외" not in caplog.text
    assert len(disconnect_messages) == 1
    assert "reason=client_disconnect" in disconnect_messages[0]


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


def test_update_review_persists_content_edit_even_if_rag_reindex_fails(db_session_factory, monkeypatch):
    """update_review()는 원래 커밋 전에 RAG 재색인(index_content)까지 끝내고 있었다
    (같은 복기에 대한 거의 동시 수정을 직렬화하는 FOR UPDATE 잠금을 재색인까지
    커버하려는 의도) - 그런데 RagService.index_content()는 실패하면 자기
    자신을 조용히 건너뛰도록 session.rollback()을 부르는데, 그게 아직 커밋
    안 된 이 복기의 content/ai_feedback 수정까지 같은 트랜잭션이라 통째로
    되돌려버렸다(143라운드). KnowledgeChunkRepository.delete_for_source를
    패치해 재색인 도중 예상 못 한 DB 오류를 재현하고, 그래도 content 수정은
    실제로 커밋되어 있는지(별도 세션으로 다시 조회) 확인한다."""
    import asyncio
    import uuid
    from datetime import date

    from app.repositories.interview_review_repository import InterviewReviewRepository
    from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
    from app.repositories.user_repository import UserRepository
    from app.services.interview_review_service import InterviewReviewService
    from app.services.rag_service import RagService

    async def _fake_delete_for_source(self, source_type, source_id):
        raise RuntimeError("boom")

    monkeypatch.setattr(KnowledgeChunkRepository, "delete_for_source", _fake_delete_for_source)

    async def _create_and_update():
        async with db_session_factory() as session:
            users = UserRepository(session)
            user = await users.create_guest()
            await session.commit()

            reviews = InterviewReviewRepository(session)
            review = await reviews.create(
                user_id=user.id,
                company="하루한",
                position="백엔드 개발자",
                interview_date=date(2024, 1, 1),
                content="원래 내용",
                model="qwen2.5:3b",
            )
            review.ai_feedback = "원래 피드백"
            await session.commit()
            review_id = review.id
            user_id = review.user_id

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=get_settings())
            service = InterviewReviewService(session=session, ollama_service=FakeOllamaService(), rag_service=rag)

            updated = await service.update_review(
                review_id=review_id,
                user_id=user_id,
                company=None,
                position=None,
                interview_date=None,
                content="수정된 내용",
            )
            return review_id, user_id, updated.content

    review_id, user_id, content_from_service_return = asyncio.run(_create_and_update())
    assert content_from_service_return == "수정된 내용"

    async def _refetch():
        async with db_session_factory() as session:
            reviews = InterviewReviewRepository(session)
            review = await reviews.get_for_user(review_id, user_id)
            return review.content if review else None

    persisted_content = asyncio.run(_refetch())
    assert persisted_content == "수정된 내용"


def test_update_review_returns_404_when_review_deleted_during_metadata_only_request(db_session_factory, monkeypatch):
    """197라운드: update_review()는 content를 안 보내는(company/position/interview_date만
    바꾸는 흔한 PATCH) 요청이면 잠금 없는 get_for_user()로 복기를 조회한다(그쪽 주석
    참고 - content_changed가 항상 False라 잠글 이유가 없다는 설계). 그런데 이 조회와
    커밋 사이에 다른 요청이 DELETE /interview/reviews/{id}로 같은 복기를 지워버리면
    UPDATE가 0행에 매치돼 StaleDataError가 나는데, 이 메서드는 그동안 그걸 잡지 않고
    있었다 - study_service.rename_session() 등 이 저장소의 다른 잠금 없는 수정
    경로는 전부 184/185라운드에서 이미 고쳐졌지만, 이 메서드의 메타데이터만-수정 분기는
    그 스윕에서 빠져 있었다(잡지 않으면 500으로 새 나간다). get_for_user()를 몽키패치해
    그 안에서 별도 세션으로 실제 삭제를 수행해 이 좁은 타이밍을 결정적으로 재현한다."""
    import asyncio
    import uuid
    from datetime import date

    from fastapi import HTTPException

    from app.repositories.interview_review_repository import InterviewReviewRepository
    from app.repositories.user_repository import UserRepository
    from app.services.interview_review_service import InterviewReviewService
    from app.services.rag_service import RagService

    async def _run():
        async with db_session_factory() as session:
            users = UserRepository(session)
            user = await users.create_guest()
            await session.commit()

            reviews = InterviewReviewRepository(session)
            review = await reviews.create(
                user_id=user.id,
                company="하루한",
                position="백엔드 개발자",
                interview_date=date(2024, 1, 1),
                content="원래 내용",
                model="qwen2.5:3b",
            )
            await session.commit()
            review_id = review.id
            user_id = user.id

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=get_settings())
            service = InterviewReviewService(session=session, ollama_service=FakeOllamaService(), rag_service=rag)

            original_get_for_user = InterviewReviewRepository.get_for_user

            async def _deleting_get_for_user(self, target_review_id, target_user_id):
                result = await original_get_for_user(self, target_review_id, target_user_id)
                async with db_session_factory() as session_b:
                    reviews_b = InterviewReviewRepository(session_b)
                    target = await original_get_for_user(reviews_b, review_id, user_id)
                    await reviews_b.delete(target)
                    await session_b.commit()
                return result

            monkeypatch.setattr(InterviewReviewRepository, "get_for_user", _deleting_get_for_user)

            try:
                await service.update_review(
                    review_id=review_id,
                    user_id=user_id,
                    company="새 회사",
                    position=None,
                    interview_date=None,
                    content=None,
                )
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 404


def test_create_review_returns_401_when_account_deleted_during_generation(db_session_factory):
    """create_review()는 AI 피드백 생성을 위한 Ollama 호출을 거쳐서야
    InterviewReview를 만든다(user_id는 nullable=False FK) - 그 사이 다른 요청이
    UserService.delete_account()로 이 계정을 지워버리면, 이 INSERT가
    IntegrityError로 실패한다. 143~145라운드가 고친 것과 같은 종류의 경쟁이다 -
    잡지 않으면 처리되지 않은 예외(500)로 새어나간다. 가짜 Ollama가 피드백을
    반환하기 "직전"에 별도 세션에서 이 계정을 완전히 지우도록 만들어서 이
    타이밍을 결정적으로 재현한다."""
    import asyncio
    from datetime import date

    from fastapi import HTTPException

    from app.repositories.user_repository import UserRepository
    from app.services.interview_review_service import InterviewReviewService
    from app.services.rag_service import RagService

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()
            user_id = user.id

            class DeletingOllamaService:
                async def chat(self, messages, model):
                    async with db_session_factory() as session_b:
                        users_b = UserRepository(session_b)
                        target = await users_b.get_by_id(user_id)
                        await users_b.delete(target)
                        await session_b.commit()
                    return "늦게 도착한 피드백"

                async def embed(self, text, model):
                    return [1.0, 0.0, 0.0]

            settings = get_settings()
            ollama = DeletingOllamaService()
            rag = RagService(session=session, ollama_service=ollama, settings=settings)
            service = InterviewReviewService(session=session, ollama_service=ollama, rag_service=rag)

            try:
                await service.create_review(
                    user_id=user_id,
                    company="하루한",
                    position="백엔드 개발자",
                    interview_date=date(2024, 1, 1),
                    content="자기소개를 했습니다.",
                    model="qwen2.5:3b",
                )
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 401


def test_stream_create_review_returns_401_when_account_deleted_during_generation(db_session_factory):
    """stream_create_review()도 create_review()와 같은 이유로 취약하다 - 스트리밍
    도중(chat_stream이 마지막 조각을 내보내기 직전) 계정이 지워지면 같은
    IntegrityError가 새어나갈 수 있다."""
    import asyncio
    from datetime import date

    from fastapi import HTTPException

    from app.repositories.user_repository import UserRepository
    from app.services.interview_review_service import InterviewReviewService
    from app.services.rag_service import RagService

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()
            user_id = user.id

            class DeletingOllamaService:
                async def chat_stream(self, messages, model):
                    yield "잘한"
                    async with db_session_factory() as session_b:
                        users_b = UserRepository(session_b)
                        target = await users_b.get_by_id(user_id)
                        await users_b.delete(target)
                        await session_b.commit()
                    yield "점입니다"

                async def embed(self, text, model):
                    return [1.0, 0.0, 0.0]

            settings = get_settings()
            ollama = DeletingOllamaService()
            rag = RagService(session=session, ollama_service=ollama, settings=settings)
            service = InterviewReviewService(session=session, ollama_service=ollama, rag_service=rag)

            try:
                async for _event_type, _data in service.stream_create_review(
                    user_id=user_id,
                    company="하루한",
                    position="백엔드 개발자",
                    interview_date=date(2024, 1, 1),
                    content="자기소개를 했습니다.",
                    model="qwen2.5:3b",
                ):
                    pass
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 401
