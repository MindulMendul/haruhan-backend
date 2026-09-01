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


def test_configured_origin_with_trailing_slash_is_still_allowed(monkeypatch):
    """Starlette의 CORSMiddleware는 Origin 헤더를 정확한 문자열로만 비교한다 -
    브라우저는 Origin 헤더에 경로를 절대 안 붙이므로, CORS_ORIGINS를 브라우저
    주소창/Vercel 도메인 목록에서 그대로 복사해 트레일링 슬래시가 붙으면
    (예: "https://example.com/") 실제 브라우저가 보내는 "https://example.com"
    과 문자열이 정확히 안 맞아 그 origin의 모든 cross-origin 요청이 조용히
    막힌다. 단순 요청과 preflight 둘 다 트레일링 슬래시가 있어도 정상적으로
    허용되는지 확인한다."""
    monkeypatch.setenv("CORS_ORIGINS", "https://example.com/")
    get_settings.cache_clear()
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/health", headers={"Origin": "https://example.com"})
        assert response.headers.get("access-control-allow-origin") == "https://example.com"

        preflight = client.options(
            "/health",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers.get("access-control-allow-origin") == "https://example.com"
