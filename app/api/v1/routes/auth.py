from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, SignupRequest, TokenResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(session=session, settings=settings)


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def signup(
    request: Request,
    payload: SignupRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return await auth_service.signup(email=payload.email, password=payload.password)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def login(
    request: Request,
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return await auth_service.login(email=payload.email, password=payload.password)


@router.post("/guest", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def create_guest(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """로그인 폼 없이 방문자마다 자동으로 익명 계정을 발급한다. 요청 바디 없음."""
    return await auth_service.create_guest_session()


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest, auth_service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    return await auth_service.refresh(refresh_token=payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest, auth_service: AuthService = Depends(get_auth_service)) -> None:
    await auth_service.logout(refresh_token=payload.refresh_token)
