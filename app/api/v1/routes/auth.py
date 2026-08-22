import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    SessionResponse,
    SignupRequest,
    TokenResponse,
)
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
    response: Response,
    payload: SignupRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return await auth_service.signup(email=payload.email, password=payload.password)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return await auth_service.login(email=payload.email, password=payload.password)


@router.post("/guest", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def create_guest(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """로그인 폼 없이 방문자마다 자동으로 익명 계정을 발급한다. 요청 바디 없음."""
    return await auth_service.create_guest_session()


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return await auth_service.refresh(refresh_token=payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def logout(
    request: Request,
    response: Response,
    payload: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    await auth_service.logout(refresh_token=payload.refresh_token)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[SessionResponse]:
    """현재 활성화된(폐기/만료되지 않은) refresh token 목록을 "세션"으로 보여준다.
    access token으로 인증하므로 지금 이 요청 자체가 어느 세션에 해당하는지는
    알 수 없다 - 세션 개수 확인, 특정/전체 세션 강제 로그아웃 용도로 쓴다."""
    sessions = await auth_service.list_active_sessions(current_user.id)
    return [SessionResponse.model_validate(s) for s in sessions]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def revoke_session(
    request: Request,
    response: Response,
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    await auth_service.revoke_session(user_id=current_user.id, session_id=session_id)


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def revoke_all_sessions(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """이 기기를 포함한 모든 기기에서 로그아웃한다 ("모든 세션 로그아웃")."""
    await auth_service.revoke_all_sessions(current_user.id)
