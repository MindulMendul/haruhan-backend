from app.core.config import get_settings
from app.core.dependencies import get_ollama_service
from app.services.ollama_service import OllamaServiceError


class FakeOllamaService:
    def __init__(self):
        self.call_count = 0

    async def chat(self, messages, model):
        self.call_count += 1
        return f"feedback-{self.call_count}"


class FailingOllamaService:
    async def chat(self, messages, model):
        raise OllamaServiceError("boom")


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
