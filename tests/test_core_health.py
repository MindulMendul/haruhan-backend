import asyncio

import app.core.health as health_module
from app.core.health import check_ollama_health, check_redis_health
from app.services.ollama_service import OllamaServiceError


class FakeRedisClient:
    """실제 Redis 서버 없이도 성공 경로(ping 응답)를 흉내내는 더블."""

    async def ping(self):
        return True

    async def aclose(self):
        pass


class SlowRedisClient:
    """PING에 응답은 하지만 아주 느린(패킷 유실 등, 완전 장애와는 다른) Redis를 흉내낸다."""

    def __init__(self, delay_seconds):
        self._delay_seconds = delay_seconds

    async def ping(self):
        await asyncio.sleep(self._delay_seconds)
        return True

    async def aclose(self):
        pass


class WorkingOllamaService:
    async def list_models(self):
        return [{"name": "qwen2.5:3b"}]


class FailingOllamaService:
    async def list_models(self):
        raise OllamaServiceError("boom")


class SlowOllamaService:
    """응답은 하지만 아주 느린(완전 장애와는 다른) Ollama를 흉내낸다."""

    def __init__(self, delay_seconds):
        self._delay_seconds = delay_seconds

    async def list_models(self):
        await asyncio.sleep(self._delay_seconds)
        return [{"name": "qwen2.5:3b"}]


def test_check_redis_health_returns_false_when_unreachable():
    # 로컬에서 아무도 안 듣는 포트라 연결이 즉시 거부된다.
    assert asyncio.run(check_redis_health("redis://localhost:6399/0", timeout_seconds=3.0)) is False


def test_check_redis_health_returns_true_when_reachable(monkeypatch):
    monkeypatch.setattr(
        health_module.redis_asyncio, "from_url", lambda url, **kwargs: FakeRedisClient()
    )
    assert asyncio.run(check_redis_health("redis://localhost:6379/0", timeout_seconds=3.0)) is True


def test_check_redis_health_passes_timeout_to_client(monkeypatch):
    """socket_connect_timeout/socket_timeout을 안 주면 redis-py 기본값(5초)을 쓰는데,
    Redis가 응답만 느려지는 상황에서 이 확인 하나가 최대 5초까지 걸릴 수 있다 -
    health_check_timeout_seconds가 실제로 그 클라이언트 생성자에 전달되는지 확인한다."""
    captured_kwargs = {}

    def _fake_from_url(url, **kwargs):
        captured_kwargs.update(kwargs)
        return FakeRedisClient()

    monkeypatch.setattr(health_module.redis_asyncio, "from_url", _fake_from_url)
    asyncio.run(check_redis_health("redis://localhost:6379/0", timeout_seconds=2.5))
    assert captured_kwargs == {"socket_connect_timeout": 2.5, "socket_timeout": 2.5}


def test_check_redis_health_returns_false_when_reachable_but_slow(monkeypatch):
    """PING 자체엔 응답하지만 너무 느린(=사실상 완전 장애와 다를 바 없는) 경우도
    짧은 타임아웃 안에 False로 판정돼야 한다 - readiness probe가 상대 서비스의
    기본 타임아웃(5초)을 그대로 물려받아 최대 5초씩 걸리는 걸 막는 게 이번 수정의
    핵심이다."""
    monkeypatch.setattr(
        health_module.redis_asyncio, "from_url", lambda url, **kwargs: SlowRedisClient(1.0)
    )
    loop = asyncio.new_event_loop()
    try:
        start = loop.time()
        result = loop.run_until_complete(
            check_redis_health("redis://localhost:6379/0", timeout_seconds=0.05)
        )
        elapsed = loop.time() - start
    finally:
        loop.close()
    assert result is False
    assert elapsed < 1.0


def test_check_ollama_health_returns_true_when_reachable():
    assert asyncio.run(check_ollama_health(WorkingOllamaService(), timeout_seconds=3.0)) is True


def test_check_ollama_health_returns_false_when_unreachable():
    assert asyncio.run(check_ollama_health(FailingOllamaService(), timeout_seconds=3.0)) is False


def test_check_ollama_health_returns_false_when_reachable_but_slow():
    """OllamaService의 기본 타임아웃(60초)을 그대로 물려받으면 응답만 느려지는
    Ollama 하나가 readiness probe를 최대 60초까지 붙잡을 수 있다 - 직접 재현해
    확인한 문제로, health_check_timeout_seconds가 실제로 짧은 상한을 거는지
    확인한다."""
    loop = asyncio.new_event_loop()
    try:
        start = loop.time()
        result = loop.run_until_complete(
            check_ollama_health(SlowOllamaService(1.0), timeout_seconds=0.05)
        )
        elapsed = loop.time() - start
    finally:
        loop.close()
    assert result is False
    assert elapsed < 1.0
