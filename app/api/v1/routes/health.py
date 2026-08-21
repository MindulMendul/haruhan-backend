from fastapi import APIRouter, Depends, Response, status

from app.core.config import Settings, get_settings
from app.core.dependencies import get_ollama_service
from app.core.health import check_ollama_health, check_redis_health
from app.db.session import check_db_health
from app.services.ollama_service import OllamaService

router = APIRouter(tags=["health"])


@router.get("/health")
def liveness() -> dict:
    """프로세스가 살아있는지만 확인 (외부 의존성 체크 없음)."""
    return {"status": "ok", "service": "haruhan-backend"}


@router.get("/health/ready")
async def readiness(
    response: Response,
    settings: Settings = Depends(get_settings),
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> dict:
    """DB/Redis/Ollama 등 외부 의존성까지 정상인지 확인. 트래픽 라우팅 판단용.

    REDIS_URL이 설정되지 않은 경우(레이트리밋이 인메모리로 동작 중) Redis는
    애초에 의존 대상이 아니므로 "not_configured"로 표시하고 전체 상태 판정에서
    제외한다.
    """
    db_ok = await check_db_health()

    redis_status = "not_configured"
    redis_ok = True
    if settings.redis_url:
        redis_ok = await check_redis_health(settings.redis_url)
        redis_status = "connected" if redis_ok else "disconnected"

    ollama_ok = await check_ollama_health(ollama_service)

    if not (db_ok and redis_ok and ollama_ok):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if (db_ok and redis_ok and ollama_ok) else "unavailable",
        "database": "connected" if db_ok else "disconnected",
        "redis": redis_status,
        "ollama": "connected" if ollama_ok else "disconnected",
    }
