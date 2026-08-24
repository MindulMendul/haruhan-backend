import asyncio
import json

from sqlalchemy import event

from app.core.config import get_settings
from app.core.dependencies import get_ollama_service
from app.repositories.user_repository import UserRepository
from app.services.ollama_service import OllamaServiceError
from app.services.quiz_service import QuizService
from app.services.rag_service import RagService

SAMPLE_QUIZ_JSON = json.dumps(
    {
        "questions": [
            {
                "question": "프로세스와 스레드의 차이는?",
                "choices": ["A", "B", "C", "D"],
                "correct_answer": "B",
                "explanation": "스레드는 프로세스 내에서 자원을 공유한다.",
            },
            {
                "question": "두 번째 질문?",
                "choices": ["가", "나", "다", "라"],
                "correct_answer": "다",
                "explanation": "설명",
            },
        ]
    }
)


class FakeOllamaService:
    async def generate_json(self, prompt, model, schema):
        return SAMPLE_QUIZ_JSON

    async def chat(self, messages, model):
        return "n/a"

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]


class MalformedJsonOllamaService:
    async def generate_json(self, prompt, model, schema):
        return "not valid json {{{"


class BadAnswerOllamaService:
    async def generate_json(self, prompt, model, schema):
        return json.dumps(
            {
                "questions": [
                    {
                        "question": "이상한 문제",
                        "choices": ["A", "B"],
                        "correct_answer": "존재하지 않는 정답",
                        "explanation": "설명",
                    }
                ]
            }
        )


class FailingOllamaService:
    async def generate_json(self, prompt, model, schema):
        raise OllamaServiceError("boom")


class RecoversOnRetryOllamaService:
    """첫 호출은 깨진 JSON을 뱉고, 두 번째 호출부터는 정상 응답을 준다."""

    def __init__(self):
        self.call_count = 0

    async def generate_json(self, prompt, model, schema):
        self.call_count += 1
        if self.call_count == 1:
            return "not valid json {{{"
        return SAMPLE_QUIZ_JSON

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]


def _signup_and_get_token(client, email="quiz@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "supersecret"}
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_quiz_from_source_text(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/quizzes",
        json={"title": "OS 퀴즈", "source_text": "프로세스와 스레드에 대한 학습 내용"},
        headers=_auth_headers(token),
    )
    assert create.status_code == 201
    quiz_id = create.json()["id"]

    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["questions"]) == 2
    assert "correct_answer" not in body["questions"][0]
    assert "explanation" not in body["questions"][0]


def test_list_quizzes_pagination(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    for i in range(5):
        client.post(
            "/api/v1/quizzes",
            json={"title": f"퀴즈 {i}", "source_text": "내용"},
            headers=_auth_headers(token),
        )

    first_page = client.get("/api/v1/quizzes?limit=2&offset=0", headers=_auth_headers(token))
    assert first_page.status_code == 200
    assert len(first_page.json()) == 2
    assert first_page.headers["X-Total-Count"] == "5"

    second_page = client.get("/api/v1/quizzes?limit=2&offset=2", headers=_auth_headers(token))
    assert len(second_page.json()) == 2

    first_ids = {q["id"] for q in first_page.json()}
    second_ids = {q["id"] for q in second_page.json()}
    assert first_ids.isdisjoint(second_ids)


def test_list_for_user_breaks_created_at_ties_deterministically():
    """`ORDER BY created_at DESC`만으로는 값이 같은 행 사이의 순서가 SQL
    표준상 정의돼 있지 않다 - 페이지마다 그 순서가 달라질 수 있어서,
    LIMIT/OFFSET으로 나눠 받으면 같은 퀴즈가 두 페이지에 다시 나오거나
    (중복) 어느 페이지에도 안 나올(누락) 수 있다. 이 동시성은 SQLite
    기반 테스트로 재현할 수 없어(68번 라운드와 같은 성격의 한계),
    리포지토리가 세션에 전달하는 statement를 가로채 컴파일된 SQL의
    ORDER BY 절에 created_at뿐 아니라 id도 2차 기준으로 포함돼 있는지
    직접 확인한다."""
    import asyncio
    import uuid

    from app.repositories.quiz_repository import QuizRepository

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
    repo = QuizRepository(session)
    asyncio.run(repo.list_for_user(uuid.uuid4(), limit=20, offset=0))

    assert session.captured_statement is not None
    order_by_clause = str(session.captured_statement).split("ORDER BY")[1]
    assert "created_at" in order_by_clause
    assert "id" in order_by_clause


def test_list_quizzes_default_pagination_returns_all_when_under_limit(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    client.post(
        "/api/v1/quizzes", json={"title": "퀴즈", "source_text": "내용"}, headers=_auth_headers(token)
    )

    listing = client.get("/api/v1/quizzes", headers=_auth_headers(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.headers["X-Total-Count"] == "1"


def test_create_quiz_requires_source(client):
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/quizzes", json={"title": "소스 없음"}, headers=_auth_headers(token)
    )
    assert response.status_code == 422


def test_create_quiz_rejects_source_text_over_max_length(client, monkeypatch):
    monkeypatch.setenv("MAX_QUIZ_SOURCE_LENGTH", "5")
    get_settings.cache_clear()
    token = _signup_and_get_token(client)

    response = client.post(
        "/api/v1/quizzes",
        json={"title": "너무 긴 소스", "source_text": "이 내용은 5자보다 훨씬 깁니다"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_create_quiz_rejects_question_count_over_max(client, monkeypatch):
    monkeypatch.setenv("MAX_QUIZ_QUESTION_COUNT", "3")
    get_settings.cache_clear()
    token = _signup_and_get_token(client)

    response = client.post(
        "/api/v1/quizzes",
        json={"title": "너무 많은 문항", "source_text": "내용", "question_count": 4},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_create_quiz_rejects_both_sources(client):
    token = _signup_and_get_token(client)
    session = client.post(
        "/api/v1/study/sessions", json={"title": "세션"}, headers=_auth_headers(token)
    )
    session_id = session.json()["id"]
    response = client.post(
        "/api/v1/quizzes",
        json={"title": "둘다", "study_session_id": session_id, "source_text": "텍스트"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_create_quiz_from_study_session(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    session = client.post(
        "/api/v1/study/sessions", json={"title": "세션"}, headers=_auth_headers(token)
    )
    session_id = session.json()["id"]

    empty = client.post(
        "/api/v1/quizzes",
        json={"title": "빈 세션 퀴즈", "study_session_id": session_id},
        headers=_auth_headers(token),
    )
    assert empty.status_code == 400

    add_message = client.post(
        f"/api/v1/study/sessions/{session_id}/messages",
        json={"content": "학습 내용입니다"},
        headers=_auth_headers(token),
    )
    assert add_message.status_code == 200

    create = client.post(
        "/api/v1/quizzes",
        json={"title": "세션 기반 퀴즈", "study_session_id": session_id},
        headers=_auth_headers(token),
    )
    assert create.status_code == 201
    assert create.json()["source_study_session_id"] == session_id


def test_quiz_from_nonexistent_session_404(client):
    token = _signup_and_get_token(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        "/api/v1/quizzes",
        json={"title": "없는 세션", "study_session_id": fake_id},
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_create_quiz_from_study_session_truncates_oversized_source_to_recent_messages(
    client, monkeypatch
):
    """max_quiz_source_length는 core/config.py 주석에도 "학습 세션 전체를 소스로
    쓸 수 있어서" 일반 프롬프트 제한보다 넉넉하게 잡았다고 돼 있는데, 정작
    study_session_id로 퀴즈를 만드는 경로에서는 이 제한이 전혀 적용되지 않고
    있었다 - QuizCreateRequest의 길이 검증은 source_text를 직접 붙여넣은
    경우에만 걸리고, 이 분기가 세션 메시지를 이어붙여 만드는 source_text는
    그 검증을 거치지 않기 때문이다. 세션 메시지 수에는 제한이 없어서, 대화가
    길어질수록 Ollama에 보내는 프롬프트가 무한정 커질 수 있었다. 사용자가
    세션 길이를 조절할 방법은 없으므로 거부 대신 가장 최근 메시지만 남기는지,
    그리고 오래된 메시지는 실제로 잘려나가는지 확인한다."""
    monkeypatch.setenv("MAX_QUIZ_SOURCE_LENGTH", "50")
    get_settings.cache_clear()

    captured_prompts = []

    class CapturingOllamaService(FakeOllamaService):
        async def generate_json(self, prompt, model, schema):
            captured_prompts.append(prompt)
            return SAMPLE_QUIZ_JSON

    client.app.dependency_overrides[get_ollama_service] = lambda: CapturingOllamaService()
    token = _signup_and_get_token(client)

    session = client.post(
        "/api/v1/study/sessions", json={"title": "긴 세션"}, headers=_auth_headers(token)
    )
    session_id = session.json()["id"]

    for i in range(5):
        response = client.post(
            f"/api/v1/study/sessions/{session_id}/messages",
            json={"content": f"오래된 메시지 내용입니다 번호는 {i}번입니다"},
            headers=_auth_headers(token),
        )
        assert response.status_code == 200

    latest = client.post(
        f"/api/v1/study/sessions/{session_id}/messages",
        json={"content": "가장 최근에 보낸 메시지입니다"},
        headers=_auth_headers(token),
    )
    assert latest.status_code == 200

    create = client.post(
        "/api/v1/quizzes",
        json={"title": "긴 세션 기반 퀴즈", "study_session_id": session_id},
        headers=_auth_headers(token),
    )
    assert create.status_code == 201

    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]
    assert "가장 최근에 보낸 메시지입니다" in prompt
    assert "번호는 0번입니다" not in prompt


def test_create_quiz_generation_failure_returns_502(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/quizzes", json={"title": "실패", "source_text": "내용"}, headers=_auth_headers(token)
    )
    assert response.status_code == 502


def test_create_quiz_malformed_json_returns_502(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: MalformedJsonOllamaService()
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/quizzes",
        json={"title": "이상한 응답", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 502


def test_create_quiz_answer_not_in_choices_returns_502(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: BadAnswerOllamaService()
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/quizzes",
        json={"title": "잘못된 정답", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 502


def test_create_quiz_retries_once_and_recovers_from_malformed_json(client):
    fake = RecoversOnRetryOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/quizzes",
        json={"title": "재시도로 성공", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    assert fake.call_count == 2


def test_submit_and_get_result(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "제출 테스트", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]

    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    questions = detail.json()["questions"]
    answers = [
        {"question_id": questions[0]["id"], "selected_index": 1},  # 정답 (B)
        {"question_id": questions[1]["id"], "selected_index": 0},  # 오답 (가)
    ]
    submit = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        json={"answers": answers},
        headers=_auth_headers(token),
    )
    assert submit.status_code == 200
    body = submit.json()
    assert body["score"] == 1
    assert body["total"] == 2

    result = client.get(f"/api/v1/quizzes/{quiz_id}/result", headers=_auth_headers(token))
    assert result.status_code == 200
    assert result.json()["score"] == 1


def test_resubmitting_identical_answers_quickly_returns_same_attempt(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "중복 제출 테스트", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]

    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    questions = detail.json()["questions"]
    answers = [
        {"question_id": questions[0]["id"], "selected_index": 1},
        {"question_id": questions[1]["id"], "selected_index": 0},
    ]

    first = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit", json={"answers": answers}, headers=_auth_headers(token)
    )
    assert first.status_code == 200

    # 네트워크 재시도 등으로 완전히 같은 답안이 곧바로 다시 제출된 상황을 흉내낸다.
    second = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit", json={"answers": answers}, headers=_auth_headers(token)
    )
    assert second.status_code == 200
    assert second.json()["attempt_id"] == first.json()["attempt_id"]
    assert second.json() == first.json()


def test_resubmitting_different_answers_quickly_creates_new_attempt(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "정상 재시도 테스트", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]

    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    questions = detail.json()["questions"]

    first = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        json={
            "answers": [
                {"question_id": questions[0]["id"], "selected_index": 1},
                {"question_id": questions[1]["id"], "selected_index": 0},
            ]
        },
        headers=_auth_headers(token),
    )
    assert first.status_code == 200

    # 답이 다르면(진짜로 다시 푼 것) 짧은 시간 안이어도 새 시도로 기록돼야 한다.
    second = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        json={
            "answers": [
                {"question_id": questions[0]["id"], "selected_index": 1},
                {"question_id": questions[1]["id"], "selected_index": 2},
            ]
        },
        headers=_auth_headers(token),
    )
    assert second.status_code == 200
    assert second.json()["attempt_id"] != first.json()["attempt_id"]


def test_submit_requires_all_questions_answered(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "부분 제출", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]
    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    questions = detail.json()["questions"]

    submit = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        json={"answers": [{"question_id": questions[0]["id"], "selected_index": 0}]},
        headers=_auth_headers(token),
    )
    assert submit.status_code == 400


def test_submit_answers_404_for_nonexistent_quiz(client):
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/quizzes/00000000-0000-0000-0000-000000000000/submit",
        json={"answers": [{"question_id": "00000000-0000-0000-0000-000000000001", "selected_index": 0}]},
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_get_for_user_locked_requests_row_lock_on_postgres():
    """submit_answers()는 "최근 5초 안에 완전히 같은 답안 제출이 있었는지"를
    확인한 뒤에야 QuizAttempt를 커밋하는 check-then-act다 - 네트워크 재시도나
    이중 클릭으로 같은 답안이 거의 동시에 두 번 제출되면, 이 잠금 없이는 두
    요청이 둘 다 "최근 제출 없음"을 보고 통과해 QuizAttempt를 두 개 만들 수
    있다. get_for_user_locked()가 실제로 FOR UPDATE를 요청하는 쿼리를 만드는지,
    세션에 전달되는 실제 statement를 가로채 확인한다(리포지토리 메서드가 하는
    일을 우회하지 않고 그대로 실행시킨다) - 나중에 누군가 `.with_for_update()`를
    실수로 지워도 이 테스트가 잡아낸다.

    SQLite는 FOR UPDATE 자체를 지원하지 않아 컴파일 시 조용히 빠져버리므로
    (직접 확인함), 이 잠금에 의존하는 동시성은 SQLite 기반 테스트 스위트로
    재현/검증할 수 없다 - 가로챈 statement를 실제로 잠그는 Postgres 방언으로
    다시 컴파일해 SQL 문자열에 "FOR UPDATE"가 포함되는지 확인하는 것으로
    대신한다(54번 라운드에서 이미 마주친 것과 같은 성격의 SQLite 한계)."""
    import asyncio
    import uuid

    from sqlalchemy.dialects import postgresql

    from app.repositories.quiz_repository import QuizRepository

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
    repo = QuizRepository(session)
    asyncio.run(repo.get_for_user_locked(uuid.uuid4(), uuid.uuid4()))

    assert session.captured_statement is not None
    compiled = str(session.captured_statement.compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in compiled


def test_submit_quiz_is_rate_limited(client, monkeypatch):
    """submit_quiz()는 LLM을 호출하지 않지만, 재도전(retake)이 정상 기능이라
    한도 없이 반복 호출되면 quiz_attempts/quiz_answers에 쓰기가 무제한으로
    쌓일 수 있었다 - 다른 의미 있는 상호작용(퀴즈/세션/면접 생성 등)과 같은
    chat_rate_limit을 적용해 이 쓰기 증폭 경로도 막는다."""
    monkeypatch.setenv("CHAT_RATE_LIMIT", "2/minute")
    get_settings.cache_clear()

    token = _signup_and_get_token(client)
    headers = _auth_headers(token)
    nonexistent_url = "/api/v1/quizzes/00000000-0000-0000-0000-000000000000/submit"
    payload = {"answers": [{"question_id": "00000000-0000-0000-0000-000000000001", "selected_index": 0}]}

    first = client.post(nonexistent_url, json=payload, headers=headers)
    second = client.post(nonexistent_url, json=payload, headers=headers)
    third = client.post(nonexistent_url, json=payload, headers=headers)

    assert first.status_code == 404
    assert second.status_code == 404
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limited"


def test_submit_answers_rejects_duplicate_question_ids(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "중복 답안 테스트", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]
    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    questions = detail.json()["questions"]

    submit = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        json={
            "answers": [
                {"question_id": questions[0]["id"], "selected_index": 0},
                {"question_id": questions[0]["id"], "selected_index": 1},
            ]
        },
        headers=_auth_headers(token),
    )
    assert submit.status_code == 400


def test_submit_answers_rejects_invalid_selected_index(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "잘못된 인덱스 테스트", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]
    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    questions = detail.json()["questions"]

    submit = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        json={
            "answers": [
                {"question_id": questions[0]["id"], "selected_index": 99},
                {"question_id": questions[1]["id"], "selected_index": 0},
            ]
        },
        headers=_auth_headers(token),
    )
    assert submit.status_code == 400


def test_result_without_submission_404(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "결과 없음", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]
    result = client.get(f"/api/v1/quizzes/{quiz_id}/result", headers=_auth_headers(token))
    assert result.status_code == 404


def test_result_404_for_nonexistent_quiz(client):
    token = _signup_and_get_token(client)
    result = client.get(
        "/api/v1/quizzes/00000000-0000-0000-0000-000000000000/result", headers=_auth_headers(token)
    )
    assert result.status_code == 404


def test_other_user_cannot_access_quiz(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token_a = _signup_and_get_token(client, email="qa@example.com")
    token_b = _signup_and_get_token(client, email="qb@example.com")

    create = client.post(
        "/api/v1/quizzes",
        json={"title": "A의 퀴즈", "source_text": "내용"},
        headers=_auth_headers(token_a),
    )
    quiz_id = create.json()["id"]

    response = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token_b))
    assert response.status_code == 404


def test_rename_quiz(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "원래 제목", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]

    rename = client.patch(
        f"/api/v1/quizzes/{quiz_id}", json={"title": "새 제목"}, headers=_auth_headers(token)
    )
    assert rename.status_code == 200
    assert rename.json()["title"] == "새 제목"

    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    assert detail.json()["title"] == "새 제목"


def test_rename_quiz_rejects_empty_title(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "원래 제목", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/quizzes/{quiz_id}", json={"title": ""}, headers=_auth_headers(token)
    )
    assert response.status_code == 422


def test_rename_quiz_404_for_nonexistent_quiz(client):
    token = _signup_and_get_token(client)
    response = client.patch(
        "/api/v1/quizzes/00000000-0000-0000-0000-000000000000",
        json={"title": "새 제목"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_rename_quiz_404_for_other_users_quiz(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token_a = _signup_and_get_token(client, email="rename-qa@example.com")
    token_b = _signup_and_get_token(client, email="rename-qb@example.com")
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "A의 퀴즈", "source_text": "내용"},
        headers=_auth_headers(token_a),
    )
    quiz_id = create.json()["id"]

    response = client.patch(
        f"/api/v1/quizzes/{quiz_id}",
        json={"title": "가로채기 시도"},
        headers=_auth_headers(token_b),
    )
    assert response.status_code == 404


def test_delete_quiz(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "삭제할 퀴즈", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]

    delete = client.delete(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    assert delete.status_code == 204

    get_after_delete = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    assert get_after_delete.status_code == 404


def test_delete_quiz_404_for_nonexistent_quiz(client):
    token = _signup_and_get_token(client)
    response = client.delete(
        "/api/v1/quizzes/00000000-0000-0000-0000-000000000000", headers=_auth_headers(token)
    )
    assert response.status_code == 404


def test_delete_quiz_404_for_other_users_quiz(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token_a = _signup_and_get_token(client, email="delete-qa@example.com")
    token_b = _signup_and_get_token(client, email="delete-qb@example.com")

    create = client.post(
        "/api/v1/quizzes",
        json={"title": "A의 퀴즈", "source_text": "내용"},
        headers=_auth_headers(token_a),
    )
    quiz_id = create.json()["id"]

    response = client.delete(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token_b))
    assert response.status_code == 404

    # 다른 사람 퀴즈는 여전히 살아있어야 한다.
    still_there = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token_a))
    assert still_there.status_code == 200


def test_delete_quiz_removes_from_list_and_wrong_answer_notebook(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "삭제 후 목록 확인", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]
    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    questions = detail.json()["questions"]

    wrong_answers = {
        "answers": [
            {"question_id": questions[0]["id"], "selected_index": 1},
            {"question_id": questions[1]["id"], "selected_index": 0},
        ]
    }
    client.post(f"/api/v1/quizzes/{quiz_id}/submit", json=wrong_answers, headers=_auth_headers(token))

    delete = client.delete(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    assert delete.status_code == 204

    listing = client.get("/api/v1/quizzes", headers=_auth_headers(token))
    assert listing.json() == []

    notebook = client.get("/api/v1/quizzes/wrong-answers", headers=_auth_headers(token))
    assert notebook.json()["entries"] == []


def test_wrong_answer_notebook_lists_wrong_questions(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "오답노트 테스트", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]
    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    questions = detail.json()["questions"]

    client.post(
        f"/api/v1/quizzes/{quiz_id}/submit",
        json={
            "answers": [
                {"question_id": questions[0]["id"], "selected_index": 1},  # 정답
                {"question_id": questions[1]["id"], "selected_index": 0},  # 오답
            ]
        },
        headers=_auth_headers(token),
    )

    notebook = client.get("/api/v1/quizzes/wrong-answers", headers=_auth_headers(token))
    assert notebook.status_code == 200
    entries = notebook.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["quiz_id"] == quiz_id
    assert entries[0]["question_id"] == questions[1]["id"]
    assert entries[0]["selected_index"] == 0
    assert entries[0]["correct_answer"] == "다"


def test_wrong_answer_notebook_skips_quizzes_with_no_attempts(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    # 한 번도 제출하지 않은 퀴즈 - 오답노트 계산 중 건너뛰어져야 한다.
    client.post(
        "/api/v1/quizzes",
        json={"title": "미제출 퀴즈", "source_text": "내용"},
        headers=_auth_headers(token),
    )

    submitted_create = client.post(
        "/api/v1/quizzes",
        json={"title": "제출한 퀴즈", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    submitted_quiz_id = submitted_create.json()["id"]
    detail = client.get(f"/api/v1/quizzes/{submitted_quiz_id}", headers=_auth_headers(token))
    questions = detail.json()["questions"]
    client.post(
        f"/api/v1/quizzes/{submitted_quiz_id}/submit",
        json={
            "answers": [
                {"question_id": questions[0]["id"], "selected_index": 1},  # 정답
                {"question_id": questions[1]["id"], "selected_index": 0},  # 오답
            ]
        },
        headers=_auth_headers(token),
    )

    notebook = client.get("/api/v1/quizzes/wrong-answers", headers=_auth_headers(token))
    assert notebook.status_code == 200
    entries = notebook.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["quiz_id"] == submitted_quiz_id


def test_wrong_answer_notebook_excludes_questions_fixed_on_retake(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "재도전 테스트", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]
    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    questions = detail.json()["questions"]

    wrong_answers = {
        "answers": [
            {"question_id": questions[0]["id"], "selected_index": 1},
            {"question_id": questions[1]["id"], "selected_index": 0},
        ]
    }
    client.post(f"/api/v1/quizzes/{quiz_id}/submit", json=wrong_answers, headers=_auth_headers(token))

    # 재도전: 이번엔 전부 맞춘다.
    correct_answers = {
        "answers": [
            {"question_id": questions[0]["id"], "selected_index": 1},
            {"question_id": questions[1]["id"], "selected_index": 2},
        ]
    }
    client.post(f"/api/v1/quizzes/{quiz_id}/submit", json=correct_answers, headers=_auth_headers(token))

    notebook = client.get("/api/v1/quizzes/wrong-answers", headers=_auth_headers(token))
    assert notebook.json()["entries"] == []


def test_wrong_answer_notebook_empty_when_no_attempts(client):
    token = _signup_and_get_token(client)
    notebook = client.get("/api/v1/quizzes/wrong-answers", headers=_auth_headers(token))
    assert notebook.status_code == 200
    assert notebook.json()["entries"] == []


def test_get_wrong_answer_notebook_issues_a_constant_number_of_queries(db_session_factory):
    """이전 구현은 퀴즈 목록을 파이썬으로 순회하며 퀴즈마다 "최근 제출"/"그
    제출의 답안"/"문항 목록" 조회를 따로 날렸다 - 퀴즈가 N개면 최대 1+3N번의
    쿼리가 나가는 N+1 패턴이었다. 윈도우 함수로 한 번에 가져오도록 바꾼 뒤,
    퀴즈가 5개 있어도 실행되는 SELECT 문이 여전히 딱 1번인지 SQLAlchemy의
    `before_cursor_execute` 이벤트로 직접 세어서 확인한다."""
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            ollama = FakeOllamaService()
            rag = RagService(session=session, ollama_service=ollama, settings=settings)
            service = QuizService(session=session, ollama_service=ollama, rag_service=rag, settings=settings)

            for i in range(5):
                quiz = await service.create_quiz(
                    user_id=user.id,
                    title=f"퀴즈 {i}",
                    study_session_id=None,
                    source_text=f"소스 {i}",
                    question_count=2,
                    model="qwen2.5:3b",
                )
                _, questions = await service.get_quiz_with_questions(quiz.id, user.id)
                wrong_index = (questions[0].choices.index(questions[0].correct_answer) + 1) % len(
                    questions[0].choices
                )
                correct_index = questions[1].choices.index(questions[1].correct_answer)
                await service.submit_answers(
                    quiz.id,
                    user.id,
                    [(questions[0].id, wrong_index), (questions[1].id, correct_index)],
                )

            select_statements: list[str] = []

            def _record_select(conn, cursor, statement, parameters, context, executemany):
                if statement.strip().upper().startswith("SELECT"):
                    select_statements.append(statement)

            engine = session.bind.sync_engine
            event.listen(engine, "before_cursor_execute", _record_select)
            try:
                entries = await service.get_wrong_answer_notebook(user.id)
            finally:
                event.remove(engine, "before_cursor_execute", _record_select)

            return entries, select_statements

    entries, select_statements = asyncio.run(_run())

    assert len(entries) == 5  # 퀴즈마다 오답 1개씩
    assert len(select_statements) == 1  # 퀴즈 개수와 무관하게 SELECT는 딱 한 번


def test_list_attempts_returns_full_history_newest_first(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "이력 테스트", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]
    detail = client.get(f"/api/v1/quizzes/{quiz_id}", headers=_auth_headers(token))
    questions = detail.json()["questions"]

    first_answers = {
        "answers": [
            {"question_id": questions[0]["id"], "selected_index": 1},  # 정답
            {"question_id": questions[1]["id"], "selected_index": 0},  # 오답
        ]
    }
    first = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit", json=first_answers, headers=_auth_headers(token)
    )
    assert first.status_code == 200

    second_answers = {
        "answers": [
            {"question_id": questions[0]["id"], "selected_index": 1},
            {"question_id": questions[1]["id"], "selected_index": 2},  # 정답 (다른 답이라 dedup 안 걸림)
        ]
    }
    second = client.post(
        f"/api/v1/quizzes/{quiz_id}/submit", json=second_answers, headers=_auth_headers(token)
    )
    assert second.status_code == 200

    attempts = client.get(f"/api/v1/quizzes/{quiz_id}/attempts", headers=_auth_headers(token))
    assert attempts.status_code == 200
    body = attempts.json()
    assert len(body) == 2
    # 최신순 - 두 번째(전부 맞음) 제출이 먼저 나와야 함.
    assert body[0]["id"] == second.json()["attempt_id"]
    assert body[0]["score"] == 2
    assert body[1]["id"] == first.json()["attempt_id"]
    assert body[1]["score"] == 1


def test_list_attempts_empty_when_never_submitted(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "미제출 퀴즈", "source_text": "내용"},
        headers=_auth_headers(token),
    )
    quiz_id = create.json()["id"]

    attempts = client.get(f"/api/v1/quizzes/{quiz_id}/attempts", headers=_auth_headers(token))
    assert attempts.status_code == 200
    assert attempts.json() == []


def test_list_attempts_404_for_nonexistent_quiz(client):
    token = _signup_and_get_token(client)
    response = client.get(
        "/api/v1/quizzes/00000000-0000-0000-0000-000000000000/attempts",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_list_attempts_404_for_other_users_quiz(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token_a = _signup_and_get_token(client, email="attempts-a@example.com")
    token_b = _signup_and_get_token(client, email="attempts-b@example.com")
    create = client.post(
        "/api/v1/quizzes",
        json={"title": "다른 사람 퀴즈", "source_text": "내용"},
        headers=_auth_headers(token_a),
    )
    quiz_id = create.json()["id"]

    response = client.get(f"/api/v1/quizzes/{quiz_id}/attempts", headers=_auth_headers(token_b))
    assert response.status_code == 404
