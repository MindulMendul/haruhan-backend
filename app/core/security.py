import secrets

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """API_KEY가 설정된 경우에만 X-API-Key 헤더를 검증한다.

    설정되지 않은 경우 인증을 건너뛴다 (로컬 개발 편의용).
    운영 환경에서는 반드시 API_KEY를 설정해 이 엔드포인트가 무방비로 노출되지 않도록 한다.
    """
    settings = get_settings()
    if not settings.api_key:
        return
    # 타이밍 공격을 막기 위해 상수 시간 비교를 사용한다.
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
