import asyncio

from fastapi import APIRouter, Depends, Response, status

from app.core.cache import TTLCache
from app.core.config import Settings, get_settings
from app.core.dependencies import get_ollama_service
from app.core.health import check_ollama_health, check_redis_health
from app.db.session import check_db_health
from app.services.ollama_service import OllamaService

router = APIRouter(tags=["health"])

# /health/ready는 인증이 없다(트래픽 라우팅 판단용으로 로드밸런서/오케스트레이터/
# 업타임 모니터가 호출하는 엔드포인트라 로그인 절차가 있으면 안 됨) - 그런데
# 매 호출마다 Ollama에 실제 HTTP 요청을 보내고(check_ollama_health) REDIS_URL이
# 설정된 경우 Redis 커넥션까지 새로 열었다 닫는다. Caddyfile은 /metrics만 막고
# 나머지는 전부 공개 도메인으로 그대로 프록시하고, docker-compose.yml의
# healthcheck도 /health(존재 확인만)만 찌르지 /health/ready는 안 건드리므로,
# 이 엔드포인트는 익명 호출자가 원하는 만큼 반복 호출할 수 있는 상태였다 -
# /models가 121라운드에서 겪은 것과 같은 모양의 문제(유일하게 인증 없는
# 엔드포인트가 반복 호출로 상류 서비스에 부하를 준다)다. 다만 이 엔드포인트는
# 본질적으로 "자주 폴링되는 것"이 정상 사용(오케스트레이터가 몇 초 간격으로
# 상태를 확인)이라, /models처럼 레이트리밋을 걸면 정상적인 헬스체크 폴링까지
# 429로 거부돼 오히려 정상 인스턴스가 "unready"로 잘못 판정될 위험이 있다 -
# 그래서 레이트리밋 대신 /models와 같은 TTLCache+락 패턴으로 짧게 캐싱해,
# 호출 빈도와 무관하게 실제 상류 호출 횟수를 이 주기당 한 번으로만 제한한다.
_READINESS_CACHE_TTL_SECONDS = 5.0
_readiness_cache: TTLCache[tuple[int, dict]] = TTLCache(ttl_seconds=_READINESS_CACHE_TTL_SECONDS)
_readiness_cache_lock = asyncio.Lock()


@router.get("/health")
def liveness() -> dict:
    """프로세스가 살아있는지만 확인 (외부 의존성 체크 없음)."""
    return {"status": "ok", "service": "haruhan-backend"}


async def _check_redis_status(settings: Settings, timeout: float) -> tuple[bool, str]:
    if not settings.redis_url:
        return True, "not_configured"
    ok = await check_redis_health(settings.redis_url, timeout)
    return ok, "connected" if ok else "disconnected"


async def _get_or_check_readiness(
    settings: Settings, ollama_service: OllamaService
) -> tuple[int, dict]:
    """캐시에 있으면 그대로 쓰고, 없으면 락을 거쳐 한 호출자만 실제로 DB/Redis/
    Ollama를 확인하고 나머지는 그 결과를 그대로 받아간다 - models.py의
    _get_or_fetch_models와 같은 이유(캐시가 막 만료된 순간 동시에 들어온
    요청들이 각자 상류 서비스를 호출하는 것을 막음)로 같은 패턴을 쓴다."""
    cached = _readiness_cache.get()
    if cached is not None:
        return cached

    async with _readiness_cache_lock:
        cached = _readiness_cache.get()
        if cached is not None:
            return cached

        timeout = settings.health_check_timeout_seconds
        # 세 확인을 각각 순서대로 await하면, 개별 확인은 health_check_timeout_seconds
        # 안에 끝나더라도(166라운드) 셋이 동시에 느려지는 실제 장애 상황(네트워크
        # 이슈 등)에서는 총 대기 시간이 그 합(최대 3배)까지 늘어난다 - readiness
        # probe는 이런 "여러 의존성이 한꺼번에 느려지는" 상황에서 오히려 가장
        # 빠르게 답해야 의미가 있는데, 오케스트레이터의 probe 자체 타임아웃(보통
        # 이 앱의 상한보다 짧게 잡힘)이 앱이 판단을 끝내기도 전에 먼저 끊어버릴
        # 수 있다. asyncio.gather로 동시에 실행해, 전체 대기 시간을 가장 느린
        # 확인 하나만큼(≈health_check_timeout_seconds)으로 되돌린다.
        db_ok, (redis_ok, redis_status), ollama_ok = await asyncio.gather(
            check_db_health(timeout),
            _check_redis_status(settings, timeout),
            check_ollama_health(ollama_service, timeout),
        )

        status_code = (
            status.HTTP_200_OK
            if (db_ok and redis_ok and ollama_ok)
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        body = {
            "status": "ok" if (db_ok and redis_ok and ollama_ok) else "unavailable",
            "database": "connected" if db_ok else "disconnected",
            "redis": redis_status,
            "ollama": "connected" if ollama_ok else "disconnected",
        }
        result = (status_code, body)
        _readiness_cache.set(result)
        return result


@router.get("/health/ready")
async def readiness(
    response: Response,
    settings: Settings = Depends(get_settings),
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> dict:
    """DB/Redis/Ollama 등 외부 의존성까지 정상인지 확인. 트래픽 라우팅 판단용.

    REDIS_URL이 설정되지 않은 경우(레이트리밋이 인메모리로 동작 중) Redis는
    애초에 의존 대상이 아니므로 "not_configured"로 표시하고 전체 상태 판정에서
    제외한다. 결과는 짧게(5초) 캐시된다 - _get_or_check_readiness 주석 참고.
    """
    status_code, body = await _get_or_check_readiness(settings, ollama_service)
    response.status_code = status_code
    return body
