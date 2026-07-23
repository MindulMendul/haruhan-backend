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


class FailingOllamaService:
    async def generate(self, prompt, model):
        raise OllamaServiceError("boom")

    async def generate_json(self, prompt, model, schema):
        raise OllamaServiceError("boom")

    async def chat(self, messages, model):
        raise OllamaServiceError("boom")


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


def test_create_session_ai_failure_returns_502(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    token = _signup_and_get_token(client)

    response = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 개발자"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 502


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
