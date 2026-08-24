import json

from app.core.config import get_settings
from app.core.dependencies import get_ollama_service

_SAMPLE_QUIZ_JSON = json.dumps(
    {
        "questions": [
            {
                "question": "질문 1",
                "choices": ["A", "B"],
                "correct_answer": "A",
                "explanation": "설명 1",
            },
            {
                "question": "질문 2",
                "choices": ["C", "D"],
                "correct_answer": "C",
                "explanation": "설명 2",
            },
        ]
    }
)


class _FakeOllamaService:
    async def generate(self, prompt, model):
        return "첫 질문"

    async def generate_json(self, prompt, model, schema):
        return _SAMPLE_QUIZ_JSON

    async def chat(self, messages, model):
        return "assistant reply"

    async def embed(self, text, model):
        return []


def _signup_and_get_token(client, email="export@example.com"):
    response = client.post("/api/v1/auth/signup", json={"email": email, "password": "supersecret"})
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_export_my_data_requires_auth(client):
    response = client.get("/api/v1/export/me")
    assert response.status_code == 401


def test_export_my_data_returns_empty_lists_for_new_user(client):
    token = _signup_and_get_token(client)
    response = client.get("/api/v1/export/me", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["study_sessions"] == []
    assert body["quizzes"] == []
    assert body["interview_practice_sessions"] == []
    assert body["interview_reviews"] == []
    assert "exported_at" in body


def test_export_my_data_includes_created_study_session(client):
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "세션"}, headers=_auth_headers(token)
    )
    assert create.status_code == 201

    response = client.get("/api/v1/export/me", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert len(body["study_sessions"]) == 1
    assert body["study_sessions"][0]["title"] == "세션"


def test_export_my_data_groups_each_entitys_children_correctly(client):
    """ExportService는 세션/퀴즈/시도마다 자식(메시지/문항/답안/턴)을 따로
    조회하던 N+1 구조를, 전부 한 번씩만 조회해 파이썬에서 부모 id별로 묶는
    방식으로 바꿨다 - 이 리팩터링에서 가장 위험한 실수는 묶는 키를 잘못
    써서 다른 세션/퀴즈/시도의 자식이 섞여 들어가는 것이다. 학습챗 세션
    2개, 퀴즈 2개(각 2번씩 재도전), 면접연습 세션 2개를 만들고, 각 항목의
    자식이 정확히 자기 것끼리만 묶였는지 id 기준으로 확인한다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: _FakeOllamaService()
    token = _signup_and_get_token(client)
    headers = _auth_headers(token)

    # 학습챗 세션 2개, 서로 다른 메시지.
    session_a = client.post(
        "/api/v1/study/sessions", json={"title": "세션 A"}, headers=headers
    ).json()
    session_b = client.post(
        "/api/v1/study/sessions", json={"title": "세션 B"}, headers=headers
    ).json()
    msg_a = client.post(
        f"/api/v1/study/sessions/{session_a['id']}/messages",
        json={"content": "A 세션 메시지"},
        headers=headers,
    ).json()
    msg_b = client.post(
        f"/api/v1/study/sessions/{session_b['id']}/messages",
        json={"content": "B 세션 메시지"},
        headers=headers,
    ).json()

    # 퀴즈 2개, 각각 문항 2개 + 서로 다른 답안 조합으로 2번 재도전(시도 2개씩).
    quiz_1 = client.post(
        "/api/v1/quizzes",
        json={"title": "퀴즈 1", "source_text": "소스 1", "model": "qwen2.5:3b"},
        headers=headers,
    ).json()
    quiz_2 = client.post(
        "/api/v1/quizzes",
        json={"title": "퀴즈 2", "source_text": "소스 2", "model": "qwen2.5:3b"},
        headers=headers,
    ).json()
    quiz_1_detail = client.get(f"/api/v1/quizzes/{quiz_1['id']}", headers=headers).json()
    quiz_2_detail = client.get(f"/api/v1/quizzes/{quiz_2['id']}", headers=headers).json()
    q1_ids = [q["id"] for q in quiz_1_detail["questions"]]
    q2_ids = [q["id"] for q in quiz_2_detail["questions"]]

    attempt_1a = client.post(
        f"/api/v1/quizzes/{quiz_1['id']}/submit",
        json={"answers": [{"question_id": q1_ids[0], "selected_index": 0}, {"question_id": q1_ids[1], "selected_index": 0}]},
        headers=headers,
    ).json()
    attempt_1b = client.post(
        f"/api/v1/quizzes/{quiz_1['id']}/submit",
        json={"answers": [{"question_id": q1_ids[0], "selected_index": 1}, {"question_id": q1_ids[1], "selected_index": 1}]},
        headers=headers,
    ).json()
    attempt_2a = client.post(
        f"/api/v1/quizzes/{quiz_2['id']}/submit",
        json={"answers": [{"question_id": q2_ids[0], "selected_index": 0}, {"question_id": q2_ids[1], "selected_index": 0}]},
        headers=headers,
    ).json()

    # 면접연습 세션 2개 (생성 시 첫 턴이 자동 생성됨).
    practice_a = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 A", "model": "qwen2.5:3b"},
        headers=headers,
    ).json()
    practice_b = client.post(
        "/api/v1/interview/practice-sessions",
        json={"topic": "백엔드 B", "model": "qwen2.5:3b"},
        headers=headers,
    ).json()

    body = client.get("/api/v1/export/me", headers=headers).json()

    sessions_by_id = {s["id"]: s for s in body["study_sessions"]}
    assert [m["content"] for m in sessions_by_id[session_a["id"]]["messages"]] == [
        "A 세션 메시지",
        "assistant reply",
    ]
    assert [m["content"] for m in sessions_by_id[session_b["id"]]["messages"]] == [
        "B 세션 메시지",
        "assistant reply",
    ]

    quizzes_by_id = {q["id"]: q for q in body["quizzes"]}
    assert {q["id"] for q in quizzes_by_id[quiz_1["id"]]["questions"]} == set(q1_ids)
    assert {q["id"] for q in quizzes_by_id[quiz_2["id"]]["questions"]} == set(q2_ids)
    assert quizzes_by_id[quiz_1["id"]]["source_text"] == "소스 1"
    assert quizzes_by_id[quiz_2["id"]]["source_text"] == "소스 2"

    quiz_1_attempt_ids = {a["id"] for a in quizzes_by_id[quiz_1["id"]]["attempts"]}
    assert quiz_1_attempt_ids == {attempt_1a["attempt_id"], attempt_1b["attempt_id"]}
    quiz_2_attempt_ids = {a["id"] for a in quizzes_by_id[quiz_2["id"]]["attempts"]}
    assert quiz_2_attempt_ids == {attempt_2a["attempt_id"]}

    attempts_by_id = {a["id"]: a for q in body["quizzes"] for a in q["attempts"]}
    assert {a["question_id"] for a in attempts_by_id[attempt_1a["attempt_id"]]["answers"]} == set(q1_ids)
    assert {a["question_id"] for a in attempts_by_id[attempt_2a["attempt_id"]]["answers"]} == set(q2_ids)

    practice_by_id = {p["id"]: p for p in body["interview_practice_sessions"]}
    assert [t["id"] for t in practice_by_id[practice_a["id"]]["turns"]] == [
        t["id"] for t in practice_a["turns"]
    ]
    assert [t["id"] for t in practice_by_id[practice_b["id"]]["turns"]] == [
        t["id"] for t in practice_b["turns"]
    ]


def test_export_includes_pasted_quiz_source_text_but_not_for_session_based_quiz(client):
    """source_text는 사용자가 직접 붙여넣은 퀴즈에서만 채워지고, 학습 세션
    기반 퀴즈는 원본이 이미 study_sessions 쪽 메시지로 export에 들어가 있으므로
    중복해서 채우지 않는다(null로 남는다) - export가 이 둘을 구분해서 정확히
    반영하는지 확인한다."""
    client.app.dependency_overrides[get_ollama_service] = lambda: _FakeOllamaService()
    token = _signup_and_get_token(client)
    headers = _auth_headers(token)

    pasted_quiz = client.post(
        "/api/v1/quizzes",
        json={"title": "붙여넣은 퀴즈", "source_text": "원본 텍스트", "model": "qwen2.5:3b"},
        headers=headers,
    ).json()

    session = client.post(
        "/api/v1/study/sessions", json={"title": "세션"}, headers=headers
    ).json()
    client.post(
        f"/api/v1/study/sessions/{session['id']}/messages",
        json={"content": "학습 내용입니다"},
        headers=headers,
    )
    session_quiz = client.post(
        "/api/v1/quizzes",
        json={"title": "세션 기반 퀴즈", "study_session_id": session["id"]},
        headers=headers,
    ).json()

    body = client.get("/api/v1/export/me", headers=headers).json()
    quizzes_by_id = {q["id"]: q for q in body["quizzes"]}

    assert quizzes_by_id[pasted_quiz["id"]]["source_text"] == "원본 텍스트"
    assert quizzes_by_id[session_quiz["id"]]["source_text"] is None


def test_export_my_data_is_rate_limited(client, monkeypatch):
    """/export/me는 학습챗/퀴즈/면접연습/면접복기 전체 기록을 페이지네이션 없이
    한 번에 조회하는 유일한 엔드포인트인데, 다른 모든 비용이 큰/쓰기 엔드포인트와
    달리 레이트리밋이 전혀 걸려 있지 않았다 - 계정 이력이 커질수록 한 번 호출
    비용도 커지는데, 반복 호출을 막을 방법이 없어 무제한 DB 부하를 유발할 수
    있었다. auth/chat 계열과 성격이 달라 분리해둔 export_rate_limit을 적용한다."""
    monkeypatch.setenv("EXPORT_RATE_LIMIT", "2/minute")
    get_settings.cache_clear()

    token = _signup_and_get_token(client)
    headers = _auth_headers(token)

    first = client.get("/api/v1/export/me", headers=headers)
    second = client.get("/api/v1/export/me", headers=headers)
    third = client.get("/api/v1/export/me", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "rate_limited"
