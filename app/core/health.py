import logging

import redis.asyncio as redis_asyncio

from app.services.ollama_service import OllamaService, OllamaServiceError

logger = logging.getLogger(__name__)


async def check_redis_health(redis_url: str) -> bool:
    """Redis에 PING을 보내 연결 가능한지 확인한다. REDIS_URL이 설정된 경우에만 호출된다."""
    client = redis_asyncio.from_url(redis_url)
    try:
        await client.ping()
        return True
    except Exception:
        logger.exception("[헬스체크] Redis 연결 실패")
        return False
    finally:
        await client.aclose()


async def check_ollama_health(ollama_service: OllamaService) -> bool:
    """Ollama 엔진이 실제로 응답 가능한지 확인한다 (모델 목록 조회로 대체)."""
    try:
        await ollama_service.list_models()
        return True
    except OllamaServiceError:
        return False
