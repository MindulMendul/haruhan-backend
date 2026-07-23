from fastapi import APIRouter, Response, status

from app.db.session import check_db_health

router = APIRouter(tags=["health"])


@router.get("/health")
def liveness() -> dict:
    """프로세스가 살아있는지만 확인 (외부 의존성 체크 없음)."""
    return {"status": "ok", "service": "haruhan-backend"}


@router.get("/health/ready")
async def readiness(response: Response) -> dict:
    """DB 등 외부 의존성까지 정상인지 확인. 트래픽 라우팅 판단용."""
    db_ok = await check_db_health()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "disconnected"}
    return {"status": "ok", "database": "connected"}
