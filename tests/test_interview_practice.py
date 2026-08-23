import json

from app.core.config import get_settings
from app.core.dependencies import get_ollama_service
from app.services.ollama_service import OllamaServiceError


class FakeOllamaService:
    async def generate(self, prompt, model):
        return "첫 번째 면접 질문입니다."

    async def generate_json(self, prompt, model, schema):
        return json.dumps({"feedback": "좋은 답변입니다.", "next_question": "다음 면접 질문입니다."})

    async def chat(self, messages, model):
        return "피드백 또는 총평 텍스트입니다."

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]


class FailingOllamaService:
    async def generate(self, prompt, model):
        raise OllamaServiceError("boom")

    async def generate_json(self, prompt, model, schema):
        raise OllamaServiceError("boom")

    async def chat(self, messages, model):
        raise OllamaServiceError("boom")

    async def embed(self, text, model):
        # RAG의 retrieve_relevant()가 chat()/generate_json() 실패보다 먼저 embed()를
        # 호출한다 - 여기서도 실패하면 원하는 502(생성 실패) 대신 embed 관련 예외가
        # 먼저 터진다. RAG 조회 자체는 정상 동작한다고 가정하고 성공시킨다.
        return [1.0, 0.0, 0.0]


class GroundingFakeOllamaService:
    """마지막으로 모델에 전달된 프롬프트를 기록해두고, 태그가 포함된 텍스트만 서로 가까운
    벡터로 임베딩한다."""

    def __init__(self):
        self.last_prompt = None

    async def generate(self, prompt, model):
        self.last_prompt = prompt
        return "질문"

    async def generate_json(self, prompt, model, schema):
        self.last_prompt = prompt
        return json.dumps({"feedback": "피드백", "next_question": "다음 질문"})

    async def chat(self, messages, model):
        self.last_prompt = messages[0]["content"]
        return "총평"

    async def embed(self, text, model):
        if "기억할 사실" in text:
            return [1.0, 0.0]
        return [0.0, 1.0]


def _signup_and_get_token(client, email="interview@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "supersecret"}
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_session_generates_first_question(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 개발자"},
        headers=_auth_headers(token),
    )
    assert create.status_code == 201
    body = create.json()
    assert body["status"] == "in_progress"
    assert len(body["turns"]) == 1
    assert body["turns"][0]["question"]
    assert body["turns"][0]["answer"] is None
    assert body["turns"][0]["feedback"] is None


def test_list_sessions_pagination(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    for i in range(5):
        client.post(
            "/api/v1/interview/practice-sessions",
            json={"topic": f"주제 {i}"},
            headers=_auth_headers(token),
        )

    first_page = client.get(
        "/api/v1/interview/practice-sessions?limit=2&offset=0", headers=_auth_headers(token)
    )
    assert first_page.status_code == 200
    assert len(first_page.json()) == 2
    assert first_page.headers["X-Total-Count"] == "5"

    second_page = client.get(
        "/api/v1/interview/practice-sessions?limit=2&offset=2", headers=_auth_headers(token)
    )
    assert len(second_page.json()) == 2

    first_ids = {s["id"] for s in first_page.json()}
    second_ids = {s["id"] for s in second_page.json()}
    assert first_ids.isdisjoint(second_ids)


def test_list_sessions_default_pagination_returns_all_when_under_limit(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    client.post(
        "/api/v1/interview/practice-sessions", json={"topic": "백엔드"}, headers=_auth_headers(token)
    )

    listing = client.get("/api/v1/interview/practice-sessions", headers=_auth_headers(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.headers["X-Total-Count"] == "1"


def test_create_session_ai_failure_returns_502(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    token = _signup_and_get_token(client)

    response = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 개발자"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 502


def test_submit_answer_rejects_answer_over_max_length(client, monkeypatch):
    monkeypatch.setenv("MAX_PROMPT_LENGTH", "5")
    get_settings.cache_clear()
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 개발자"},
        headers=_auth_headers(token),
    )
    session_id = create.json()["id"]

    response = client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/answers",
        json={"answer": "이 답변은 5자보다 훨씬 깁니다"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 422


def test_submit_answer_returns_feedback_and_next_question(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 개발자"},
        headers=_auth_headers(token),
    )
    session_id = create.json()["id"]

    answer = client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/answers",
        json={"answer": "이렇게 답변하겠습니다."},
        headers=_auth_headers(token),
    )
    assert answer.status_code == 200
    body = answer.json()
    assert body["answered_turn"]["answer"] == "이렇게 답변하겠습니다."
    assert body["answered_turn"]["feedback"]
    assert body["next_turn"] is not None
    assert body["next_turn"]["question"]

    detail = client.get(
        f"/api/v1/interview/practice-sessions/{session_id}", headers=_auth_headers(token)
    )
    assert len(detail.json()["turns"]) == 2


def test_reaching_max_questions_stops_next_question(client, monkeypatch):
    monkeypatch.setenv("MAX_INTERVIEW_QUESTIONS", "1")
    get_settings.cache_clear()
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 개발자"},
        headers=_auth_headers(token),
    )
    session_id = create.json()["id"]

    answer = client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/answers",
        json={"answer": "마지막 답변입니다."},
        headers=_auth_headers(token),
    )
    assert answer.status_code == 200
    body = answer.json()
    assert body["next_turn"] is None
    assert body["answered_turn"]["feedback"]

    # 더 이상 답변할 질문이 없어야 한다.
    no_pending = client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/answers",
        json={"answer": "더 이상 없음"},
        headers=_auth_headers(token),
    )
    assert no_pending.status_code == 409


def test_submit_answer_404_for_nonexistent_session(client):
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/interview/practice-sessions/00000000-0000-0000-0000-000000000000/answers",
        json={"answer": "답변"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_submit_answer_ai_failure_returns_502(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 개발자"},
        headers=_auth_headers(token),
    )
    session_id = create.json()["id"]

    # 다음 질문을 생성해야 하는(마지막 턴이 아닌) 경로에서 AI 호출이 실패하는 경우.
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    response = client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/answers",
        json={"answer": "답변"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 502


def test_submit_answer_at_final_turn_ai_failure_returns_502(client, monkeypatch):
    monkeypatch.setenv("MAX_INTERVIEW_QUESTIONS", "1")
    get_settings.cache_clear()
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 개발자"},
        headers=_auth_headers(token),
    )
    session_id = create.json()["id"]

    # 마지막 턴(다음 질문 없이 종합 피드백만 생성)에서 AI 호출이 실패하는 경우.
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    response = client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/answers",
        json={"answer": "마지막 답변"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 502


def test_complete_session_404_for_nonexistent_session(client):
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/interview/practice-sessions/00000000-0000-0000-0000-000000000000/complete",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_complete_session_ai_failure_returns_502(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 개발자"},
        headers=_auth_headers(token),
    )
    session_id = create.json()["id"]
    client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/answers",
        json={"answer": "답변"},
        headers=_auth_headers(token),
    )

    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    response = client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/complete", headers=_auth_headers(token)
    )
    assert response.status_code == 502


def test_complete_session_generates_overall_feedback(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 개발자"},
        headers=_auth_headers(token),
    )
    session_id = create.json()["id"]

    client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/answers",
        json={"answer": "답변"},
        headers=_auth_headers(token),
    )

    complete = client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/complete", headers=_auth_headers(token)
    )
    assert complete.status_code == 200
    body = complete.json()
    assert body["status"] == "completed"
    assert body["overall_feedback"]

    # 이미 종료된 세션은 다시 종료할 수 없고, 답변도 더 이상 제출할 수 없다.
    complete_again = client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/complete", headers=_auth_headers(token)
    )
    assert complete_again.status_code == 409

    answer_after_complete = client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/answers",
        json={"answer": "종료 후 답변"},
        headers=_auth_headers(token),
    )
    assert answer_after_complete.status_code == 409


def test_complete_session_is_rate_limited(client, monkeypatch):
    """complete_session()은 내부적으로 종합 피드백을 생성하려고 LLM(ollama.chat)을
    호출하는데도, create_session/submit_answer와 달리 라우트에 @limiter.limit()이
    빠져 있었다 - LLM 호출 비용을 막으려고 두는 chat_rate_limit이 이 경로에는
    전혀 적용되지 않던 누락이었다. 데코레이터는 핸들러 본문(404/409 등) 실행
    전에 카운트를 소비하므로, 존재하지 않는 세션 id로 반복 호출해도 레이트리밋은
    그대로 걸려야 한다."""
    monkeypatch.setenv("CHAT_RATE_LIMIT", "2/minute")
    get_settings.cache_clear()

    token = _signup_and_get_token(client, email="complete-ratelimit@example.com")
    headers = _auth_headers(token)
    nonexistent_url = "/api/v1/interview/practice-sessions/00000000-0000-0000-0000-000000000000/complete"

    first = client.post(nonexistent_url, headers=headers)
    second = client.post(nonexistent_url, headers=headers)
    third = client.post(nonexistent_url, headers=headers)

    assert first.status_code == 404
    assert second.status_code == 404
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limited"


def test_complete_without_any_answer_returns_400(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 개발자"},
        headers=_auth_headers(token),
    )
    session_id = create.json()["id"]

    complete = client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/complete", headers=_auth_headers(token)
    )
    assert complete.status_code == 400


def test_first_session_has_no_grounding_when_corpus_is_empty(client):
    fake = GroundingFakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)

    client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "일반 주제"},
        headers=_auth_headers(token),
    )

    assert fake.last_prompt is not None
    assert "[참고자료]" not in fake.last_prompt


def test_later_session_is_grounded_with_relevant_legacy_content(client):
    fake = GroundingFakeOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "일반 주제"},
        headers=_auth_headers(token),
    )
    session_id = create.json()["id"]

    client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/answers",
        json={"answer": "기억할 사실: 스레드는 프로세스 안에서 돈다"},
        headers=_auth_headers(token),
    )

    client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "기억할 사실 관련 질문"},
        headers=_auth_headers(token),
    )

    assert "[참고자료]" in fake.last_prompt
    assert "기억할 사실: 스레드는 프로세스 안에서 돈다" in fake.last_prompt


def test_other_user_cannot_access_session(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token_a = _signup_and_get_token(client, email="ia@example.com")
    token_b = _signup_and_get_token(client, email="ib@example.com")

    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "A의 면접"},
        headers=_auth_headers(token_a),
    )
    session_id = create.json()["id"]

    response = client.get(
        f"/api/v1/interview/practice-sessions/{session_id}", headers=_auth_headers(token_b)
    )
    assert response.status_code == 404


def test_delete_session(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="delete-practice@example.com")

    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "삭제할 면접"},
        headers=_auth_headers(token),
    )
    session_id = create.json()["id"]

    delete = client.delete(
        f"/api/v1/interview/practice-sessions/{session_id}", headers=_auth_headers(token)
    )
    assert delete.status_code == 204

    get_after_delete = client.get(
        f"/api/v1/interview/practice-sessions/{session_id}", headers=_auth_headers(token)
    )
    assert get_after_delete.status_code == 404

    listing = client.get("/api/v1/interview/practice-sessions", headers=_auth_headers(token))
    assert listing.json() == []


def test_delete_session_404_for_nonexistent_session(client):
    token = _signup_and_get_token(client, email="delete-practice-404@example.com")
    response = client.delete(
        "/api/v1/interview/practice-sessions/00000000-0000-0000-0000-000000000000",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_delete_session_404_for_other_users_session(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token_a = _signup_and_get_token(client, email="delete-practice-a@example.com")
    token_b = _signup_and_get_token(client, email="delete-practice-b@example.com")

    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "A의 면접"},
        headers=_auth_headers(token_a),
    )
    session_id = create.json()["id"]

    response = client.delete(
        f"/api/v1/interview/practice-sessions/{session_id}", headers=_auth_headers(token_b)
    )
    assert response.status_code == 404

    still_there = client.get(
        f"/api/v1/interview/practice-sessions/{session_id}", headers=_auth_headers(token_a)
    )
    assert still_there.status_code == 200


def test_delete_session_with_answered_turns(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="delete-practice-answered@example.com")

    create = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "답변 있는 면접"},
        headers=_auth_headers(token),
    )
    session_id = create.json()["id"]
    client.post(
        f"/api/v1/interview/practice-sessions/{session_id}/answers",
        json={"answer": "제 답변입니다."},
        headers=_auth_headers(token),
    )

    delete = client.delete(
        f"/api/v1/interview/practice-sessions/{session_id}", headers=_auth_headers(token)
    )
    assert delete.status_code == 204
