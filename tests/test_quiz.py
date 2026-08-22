import json

from app.core.config import get_settings
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
