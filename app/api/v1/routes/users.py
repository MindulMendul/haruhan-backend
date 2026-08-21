from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.user import AccountDeletionRequest, GuestUpgradeRequest, UserResponse, UserUpdateRequest
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/me", response_model=UserResponse)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def update_me(
    request: Request,
    response: Response,
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    service = UserService(session=session)
    return await service.update_profile(
        user=current_user,
        email=payload.email,
        password=payload.password,
        current_password=payload.current_password,
    )


@router.post("/me/upgrade", response_model=UserResponse)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def upgrade_guest(
    request: Request,
    response: Response,
    payload: GuestUpgradeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> User:
    service = UserService(session=session)
    return await service.upgrade_guest(user=current_user, email=payload.email, password=payload.password)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(lambda: get_settings().auth_rate_limit)
async def delete_me(
    request: Request,
    response: Response,
    payload: AccountDeletionRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """내 계정과 연관 데이터(학습챗/퀴즈/면접연습/면접복기 등) 전체를 영구 삭제한다."""
    service = UserService(session=session)
    await service.delete_account(user=current_user, current_password=payload.current_password)
