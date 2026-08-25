import logging
import uuid

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.tokens import create_access_token
from app.main import create_app


def test_body_size_limit_rejects_large_payload(monkeypatch):
    monkeypatch.setenv("MAX_BODY_SIZE_BYTES", "10")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/chat", json={"prompt": "this payload is definitely longer than 10 bytes"}
        )
    assert response.status_code == 413
    # 이 미들웨어는 FastAPI 예외 핸들러를 안 거치는 ASGI 레벨 응답이라, 나머지
    # 에러들과 같은 {"error": {"code", "message"}} 포맷을 직접 챙겨줘야 한다 -
    # 예전엔 {"detail": "..."}로 혼자 통일 안 된 채 남아있던 회귀가 있었다.
    body = response.json()
    assert body["error"]["code"] == "payload_too_large"


def test_body_size_limit_ignores_malformed_content_length_header(monkeypatch):
    """이 미들웨어는 FastAPI 라우팅/예외 핸들러보다 바깥(ASGI 계층)에서 직접
    Content-Length를 파싱한다 - 예전엔 `int(content_length)`를 그대로 불러서,
    숫자가 아닌 값(오타, 스캐너/프록시가 보내는 이상한 값 등)이 오면
    처리되지 않은 ValueError가 main.py의 전역 핸들러까지 올라가 500으로
    끝났다 - 대용량 payload를 막으려는 방어용 미들웨어 자신이 아무 malformed
    헤더에나 500을 만들어내는 셈이었다. 숫자로 파싱할 수 없는 값은 크기를
    알 수 없는 것으로 취급해(이 미들웨어가 원래도 못 막는 chunked 요청과
    같은 취급) 요청이 정상적으로 통과하는지 확인한다."""
    monkeypatch.setenv("MAX_BODY_SIZE_BYTES", "1048576")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/health", headers={"content-length": "abc"})
    assert response.status_code == 200


def test_body_size_limit_allows_small_payload(monkeypatch):
    monkeypatch.setenv("MAX_BODY_SIZE_BYTES", "1048576")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200


def _attach_caplog_to_access_logger(caplog):
    # create_app()이 내부에서 configure_logging()을 force=True로 호출하는데,
    # 이는 root logger의 핸들러를 전부 지워버려서 pytest의 caplog 핸들러도
    # 함께 떨어져 나간다. create_app() 이후에 caplog 핸들러를 "haruhan.access"
    # 로거에 직접 다시 붙여줘야 로그가 잡힌다.
    access_logger = logging.getLogger("haruhan.access")
    access_logger.addHandler(caplog.handler)
    access_logger.setLevel(logging.INFO)
    return access_logger


def test_access_log_middleware_logs_anonymous_request(caplog):
    app = create_app()
    access_logger = _attach_caplog_to_access_logger(caplog)
    try:
        with TestClient(app) as client:
            response = client.get("/health")
    finally:
        access_logger.removeHandler(caplog.handler)
    assert response.status_code == 200

    records = [r for r in caplog.records if r.name == "haruhan.access"]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "method=GET" in message
    assert "path=/health" in message
    assert "status=200" in message
    assert "duration_ms=" in message
    assert "user_id=-" in message


def test_access_log_middleware_logs_authenticated_user_id(caplog):
    app = create_app()
    settings = get_settings()
    user_id = uuid.uuid4()
    token = create_access_token(user_id, settings)

    access_logger = _attach_caplog_to_access_logger(caplog)
    try:
        with TestClient(app) as client:
            response = client.get(
                "/health", headers={"Authorization": f"Bearer {token}"}
            )
    finally:
        access_logger.removeHandler(caplog.handler)
    assert response.status_code == 200

    records = [r for r in caplog.records if r.name == "haruhan.access"]
    assert len(records) == 1
    assert f"user_id={user_id}" in records[0].getMessage()


def test_access_log_middleware_logs_anonymous_for_non_bearer_scheme(caplog):
    """user_id 추출은 로깅용 부가 정보일 뿐이다 - Bearer가 아닌 인증 스킴(예: Basic)이
    와도 요청을 막지 않고 조용히 user_id 없음으로 처리해야 한다."""
    app = create_app()
    access_logger = _attach_caplog_to_access_logger(caplog)
    try:
        with TestClient(app) as client:
            response = client.get("/health", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    finally:
        access_logger.removeHandler(caplog.handler)
    assert response.status_code == 200

    records = [r for r in caplog.records if r.name == "haruhan.access"]
    assert len(records) == 1
    assert "user_id=-" in records[0].getMessage()
