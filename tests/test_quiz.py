import json

from app.core.dependencies import get_ollama_service
from app.services.ollama_service import OllamaServiceError

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


def test_create_quiz_requires_source(client):
    token = _signup_and_get_token(client)
    response = client.post(
        "/api/v1/quizzes", json={"title": "소스 없음"}, headers=_auth_headers(token)
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
