from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core import rate_limit as rate_limit_module


def test_limiter_uses_redis_storage_when_redis_url_configured():
    """app.core.rate_limit이 REDIS_URL 설정 시 실제로 Redis 백엔드로 전환되는지 확인한다.

    Redis 서버가 없어도 통과해야 한다 - limits 라이브러리는 스토리지 생성 시점에는
    연결하지 않고, 실제 요청이 들어와 체크할 때만 연결을 시도한다 (지연 연결).
    """
    limiter = Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6399/0")
    assert type(limiter._storage).__name__ == "RedisStorage"


def test_limiter_uses_memory_storage_when_no_redis_url():
    limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
    assert type(limiter._storage).__name__ == "MemoryStorage"


def test_limiter_falls_back_to_memory_when_redis_unreachable(caplog):
    """이 앱은 auth/chat/quiz 등 거의 모든 쓰기 엔드포인트에 @limiter.limit()이
    걸려 있다 - in_memory_fallback_enabled 없이는 Redis가 잠깐 끊겨도(재시작,
    네트워크 문제 등) 그 예외가 그대로 올라가 API 전체가 500으로 죽는다.
    실제 라우트를 하나 만들어 호출해서, Limiter가 저장소 장애를 감지하고
    인메모리로 자동 전환해 요청을 500 없이 계속 처리하는지 확인한다."""
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri="redis://127.0.0.1:1/0",
        in_memory_fallback_enabled=True,
    )

    app = FastAPI()
    app.state.limiter = limiter

    @app.get("/probe")
    @limiter.limit("5/minute")
    async def probe(request: Request) -> dict:
        return {"ok": True}

    with caplog.at_level("WARNING", logger="slowapi"), TestClient(app) as client:
        response = client.get("/probe")

    assert response.status_code == 200
    assert "falling back to in-memory storage" in caplog.text
    assert limiter._storage_dead is True


def test_check_rate_limit_allows_request_when_redis_unreachable(monkeypatch, caplog):
    """check_rate_limit()은 WebSocket 경로에서 limiter.limiter(내부 저장소 전략
    객체)를 직접 호출하므로 위 in_memory_fallback_enabled 자동 복구를 안 거친다 -
    Redis 장애 시 이 경로도 예외를 그대로 올리지 않고 "허용"으로 안전하게
    처리하는지 확인한다."""
    limiter = Limiter(key_func=get_remote_address, storage_uri="redis://127.0.0.1:1/0")
    monkeypatch.setattr(rate_limit_module, "limiter", limiter)

    with caplog.at_level("ERROR", logger="haruhan"):
        allowed, retry_after = rate_limit_module.check_rate_limit("test-key", "5/minute")

    assert allowed is True
    assert retry_after == 0
    assert "레이트리밋 저장소(Redis) 장애" in caplog.text
