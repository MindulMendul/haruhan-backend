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


def test_validation_error_details_do_not_leak_raw_input(client):
    """RequestValidationError.errors()는 검증 실패 필드의 원본 값을 "input"으로
    그대로 담고 있다 - password처럼 짧아서 검증에 실패한 민감한 값이 422 응답
    바디에 평문으로 실려 나가면 안 된다. loc/type/msg 같은 프론트가 실제로 쓰는
    필드는 여전히 남아 있어야 한다."""
    response = client.post(
        "/api/v1/auth/signup", json={"email": "leak@example.com", "password": "short"}
    )
    assert response.status_code == 422
    body = response.json()
    details = body["error"]["details"]
    assert len(details) > 0
    for error in details:
        assert "input" not in error
    assert any(error["loc"] == ["body", "password"] for error in details)
    assert '"input"' not in response.text


def test_ollama_service_error_returns_internal_error_code(client):
    """/api/v1/chat 라우트가 OllamaServiceError를 명시적으로 잡아 HTTPException(500,
    detail=str(exc))로 바꾸는 경로 - 문자열 detail이라 상태코드 기반 기본
    code(internal_error)로 떨어진다. app.main의 전역 catch-all
    (@app.exception_handler(Exception))과는 다른 경로다 - 그건 아래
    test_truly_unhandled_exception_hits_global_catch_all이 검증한다."""

    class FailingOllamaService:
        async def generate(self, prompt, model):
            raise OllamaServiceError("boom")

    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()
    response = client.post("/api/v1/chat", json={"prompt": "hello"})

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"


def test_truly_unhandled_exception_hits_global_catch_all():
    """라우트가 잡지 않는 예상 못한 예외(OllamaServiceError가 아닌 임의의
    예외)는 어떤 핸들러도 못 잡고 app.main의 전역 catch-all까지 올라가야
    한다 - 스택 트레이스가 그대로 노출되지 않고 항상 통일된 500 바디로
    응답하는지 확인한다."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    class CrashingOllamaService:
        async def generate(self, prompt, model):
            raise RuntimeError("완전히 예상 못한 버그")

    app = create_app()
    app.dependency_overrides[get_ollama_service] = lambda: CrashingOllamaService()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/chat", json={"prompt": "hello"})

    assert response.status_code == 500
    body = response.json()
    assert body["error"] == {"code": "internal_error", "message": "Internal server error"}


def _signup_token(client, email="errfmt@example.com"):
    response = client.post("/api/v1/auth/signup", json={"email": email, "password": "supersecret"})
    assert response.status_code == 201
    return response.json()["access_token"]
