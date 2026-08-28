import logging

from fastapi.testclient import TestClient

from app.main import create_app


def test_startup_warns_with_correct_chat_route_when_api_key_unset(caplog, monkeypatch):
    """API_KEY 미설정 시 뜨는 경고 로그가 실제 라우트 경로를 가리키는지 확인한다.
    이 프록시 엔드포인트는 API 버전 프리픽스가 도입된 이후 계속
    `/api/v1/chat`이었는데, 이 경고 메시지(와 core/config.py의 두 주석)는
    `/api/v1` 프리픽스 없이 `/api/chat`을 가리키고 있었다 - 운영자가 실제로
    읽는 로그가 존재하지 않는 경로를 가리키는 순수 문서/로그 정확성
    버그였다."""
    monkeypatch.delenv("API_KEY", raising=False)

    app = create_app()
    # create_app()이 configure_logging()을 force=True로 호출해 root logger
    # 핸들러를 전부 지우므로(test_middleware.py의 같은 패턴 참고), create_app()
    # 이후에 caplog 핸들러를 "haruhan" 로거에 다시 붙여야 lifespan 시작 시
    # 남기는 이 경고를 잡을 수 있다.
    logger = logging.getLogger("haruhan")
    logger.addHandler(caplog.handler)
    logger.setLevel(logging.WARNING)
    try:
        with TestClient(app):
            pass
    finally:
        logger.removeHandler(caplog.handler)

    assert "/api/v1/chat" in caplog.text
    assert "/api/chat 인증" not in caplog.text
