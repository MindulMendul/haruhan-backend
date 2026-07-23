from app.core.dependencies import get_ollama_service
from app.services.ollama_service import OllamaServiceError


class FakeOllamaService:
    async def chat(self, messages, model):
        return f"assistant reply to: {messages[-1]['content']}"


class FailingOllamaService:
    async def chat(self, messages, model):
        raise OllamaServiceError("boom")


def _signup_and_get_token(client, email="study@example.com"):
    response = client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "supersecret"}
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


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
    assert send.status_code == 500

    detail = client.get(f"/api/v1/study/sessions/{session_id}", headers=_auth_headers(token))
    messages = detail.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "이 메시지는 저장돼야 한다"
