from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_pagination_and_rate_limit_headers_are_exposed_to_cross_origin_js(monkeypatch):
    """브라우저는 CORS-safelisted 헤더 몇 개만 fetch()의 response.headers로
    기본 노출하고, 그 외는 서버가 Access-Control-Expose-Headers로 명시해야
    JS가 읽을 수 있다. FRONTEND_INTEGRATION.md가 프론트더러 직접 읽으라고
    안내하는 X-Total-Count/X-RateLimit-*/Retry-After가 실제로 노출 목록에
    있는지 확인한다 - 이 프로젝트의 실제 배포 형태(Vercel 프론트가 다른
    도메인의 이 API를 호출)에서는 CORS가 항상 적용되므로 실제로 중요하다.
    """
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
    get_settings.cache_clear()
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": "https://example.com"})

    assert response.status_code == 200
    exposed = response.headers.get("access-control-expose-headers", "")
    exposed_headers = {h.strip() for h in exposed.split(",")}
    assert exposed_headers == {
        "X-Total-Count",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
    }


def test_configured_origin_is_allowed(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
    get_settings.cache_clear()
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": "https://example.com"})

    assert response.headers.get("access-control-allow-origin") == "https://example.com"


def test_unlisted_origin_is_not_allowed(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com")
    get_settings.cache_clear()
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers
