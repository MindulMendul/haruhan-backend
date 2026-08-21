import asyncio

from app.core.health import check_ollama_health, check_redis_health
from app.services.ollama_service import OllamaServiceError


class WorkingOllamaService:
    async def list_models(self):
        return [{"name": "qwen2.5:3b"}]


class FailingOllamaService:
    async def list_models(self):
        raise OllamaServiceError("boom")


def test_check_redis_health_returns_false_when_unreachable():
    # 로컬에서 아무도 안 듣는 포트라 연결이 즉시 거부된다.
    assert asyncio.run(check_redis_health("redis://localhost:6399/0")) is False


def test_check_ollama_health_returns_true_when_reachable():
    assert asyncio.run(check_ollama_health(WorkingOllamaService())) is True


def test_check_ollama_health_returns_false_when_unreachable():
    assert asyncio.run(check_ollama_health(FailingOllamaService())) is False
