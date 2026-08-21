from app.core.dependencies import get_ollama_service
from app.services.ollama_service import OllamaServiceError


def test_plain_string_detail_gets_status_based_default_code(client):
    response = client.post(
        "/api/v1/quizzes",
        json={"title": "제목", "study_session_id": "00000000-0000-0000-0000-000000000000"},
        headers={"Authorization": f"Bearer {_signup_token(client)}"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == "Study session not found"


def test_structured_detail_keeps_explicit_code(client):
    _signup_token(client, email="errfmt-login@example.com")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "errfmt-login@example.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"] == {"code": "invalid_credentials", "message": "Invalid email or password"}


def test_invalid_token_uses_explicit_code(client):
    response = client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "invalid_token"


def test_validation_error_includes_details(client):
    response = client.post("/api/v1/auth/signup", json={"email": "not-an-email"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list)
    assert len(body["error"]["details"]) > 0


def test_unhandled_exception_returns_internal_error_code():
    from fastapi.testclient import TestClient

    from app.main import create_app

    class FailingOllamaService:
        async def generate(self, prompt, model):
            raise OllamaServiceError("boom")

    app = create_app()
    app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    with TestClient(app) as client:
        response = client.post("/api/v1/chat", json={"prompt": "hello"})

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"


def _signup_token(client, email="errfmt@example.com"):
    response = client.post("/api/v1/auth/signup", json={"email": email, "password": "supersecret"})
    assert response.status_code == 201
    return response.json()["access_token"]
