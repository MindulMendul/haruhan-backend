import asyncio
import logging

import redis.asyncio as redis_asyncio

from app.services.ollama_service import OllamaService, OllamaServiceError

logger = logging.getLogger(__name__)


async def check_redis_health(redis_url: str, timeout_seconds: float) -> bool:
    """Redis에 PING을 보내 연결 가능한지 확인한다. REDIS_URL이 설정된 경우에만 호출된다.

    socket_timeout/socket_connect_timeout을 주지 않으면 redis-py 기본값(5초)을
    쓰는데, Redis가 완전히 죽은 게 아니라 응답만 느려지는 상황에서는 이 확인 하나가
    최대 5초까지 걸릴 수 있다 - readiness probe는 빠르게 답해야 의미가 있으므로,
    core/config.py의 health_check_timeout_seconds로 이 앱 전체가 공유하는 짧은
    상한을 건다(rate_limit.py의 REDIS_SOCKET_TIMEOUT_SECONDS와 같은 이유). 소켓
    옵션만으로는 라이브러리 내부 구현에 기대는 셈이라, check_ollama_health/
    check_db_health와 똑같이 asyncio.wait_for로 한 번 더 상한을 걸어둔다.
    """
    client = redis_asyncio.from_url(
        redis_url, socket_connect_timeout=timeout_seconds, socket_timeout=timeout_seconds
    )
    try:
        await asyncio.wait_for(client.ping(), timeout=timeout_seconds)
        return True
    except Exception:
        logger.exception("[헬스체크] Redis 연결 실패")
        return False
    finally:
        await client.aclose()


async def check_ollama_health(ollama_service: OllamaService, timeout_seconds: float) -> bool:
    """Ollama 엔진이 실제로 응답 가능한지 확인한다 (모델 목록 조회로 대체).

    ollama_service는 기본 60초 타임아웃으로 만들어지는데, Ollama가 완전히 죽은
    게 아니라 응답만 느려지는 상황(GPU 과부하, 네트워크 지연 등)에서는 이
    확인 하나가 최대 60초까지 걸릴 수 있다 - check_redis_health와 같은 이유로
    health_check_timeout_seconds로 짧은 상한을 건다.
    """
    try:
        await asyncio.wait_for(ollama_service.list_models(), timeout=timeout_seconds)
        return True
    except (OllamaServiceError, asyncio.TimeoutError):
        return False
