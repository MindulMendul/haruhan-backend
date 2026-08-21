from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.core.config import Settings
from app.core.metrics import user_signups_total
from app.core.password import PasswordTooLongError, hash_password, verify_password
from app.core.tokens import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
)
from app.db.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
)
_INVALID_REFRESH_TOKEN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
)


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)

    async def signup(self, email: str, password: str) -> TokenResponse:
        existing = await self._users.get_by_email(email)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        try:
            hashed = hash_password(password)
        except PasswordTooLongError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        user = await self._users.create(email=email, hashed_password=hashed)
        tokens = await self._issue_tokens(user)
        await self._session.commit()
        user_signups_total.inc()
        return tokens

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self._users.get_by_email(email)
        # 게스트는 email이 없어 여기 도달할 일이 없지만(hashed_password도 항상 None),
        # 방어적으로 명시 검사한다.
        if user is None or user.hashed_password is None or not verify_password(password, user.hashed_password):
            raise _INVALID_CREDENTIALS

        tokens = await self._issue_tokens(user)
        await self._session.commit()
        return tokens

    async def refresh(self, refresh_token: str) -> TokenResponse:
        token_hash = hash_refresh_token(refresh_token)
        stored = await self._refresh_tokens.get_by_hash(token_hash)
        if stored is None:
            raise _INVALID_REFRESH_TOKEN

        if stored.revoked_at is not None:
            # 이미 폐기된(=한 번 로테이션됐거나 로그아웃된) 토큰이 다시 제시됐다 - 탈취
            # 의심 신호다. 정상 사용자라면 로테이션된 최신 토큰을 쓰고 있을 테니, 이
            # 낡은 토큰이 다시 나타났다는 건 누군가 훔쳐 쓰고 있을 가능성이 크다.
            # 공격자와 정상 사용자 모두 강제 로그아웃시켜 세션을 안전한 상태로 되돌린다.
            await self._refresh_tokens.revoke_all_for_user(stored.user_id)
            await self._session.commit()
            raise _INVALID_REFRESH_TOKEN

        if stored.expires_at <= utcnow_naive():
            raise _INVALID_REFRESH_TOKEN

        user = await self._users.get_by_id(stored.user_id)
        if user is None:
            raise _INVALID_REFRESH_TOKEN

        # 토큰 로테이션: 사용된 refresh token은 즉시 폐기하고 새 쌍을 발급한다.
        await self._refresh_tokens.revoke(stored)
        tokens = await self._issue_tokens(user)
        await self._session.commit()
        return tokens

    async def create_guest_session(self) -> TokenResponse:
        """로그인 폼 없이 방문자마다 자동으로 익명 계정을 만들고 토큰을 발급한다.

        이 토큰/refresh_token을 클라이언트가 잃어버리면(로그아웃, 스토리지 삭제 등)
        해당 게스트 계정의 데이터는 다시 접근할 방법이 없다 - 별도의 이메일/비밀번호가
        없기 때문이다. 이후 실제 계정으로 전환하는 기능은 아직 없다.
        """
        user = await self._users.create_guest()
        tokens = await self._issue_tokens(user)
        await self._session.commit()
        return tokens

    async def logout(self, refresh_token: str) -> None:
        token_hash = hash_refresh_token(refresh_token)
        stored = await self._refresh_tokens.get_by_hash(token_hash)
        if stored is not None and stored.revoked_at is None:
            await self._refresh_tokens.revoke(stored)
        await self._session.commit()

    async def _issue_tokens(self, user: User) -> TokenResponse:
        access_token = create_access_token(user.id, self._settings)
        raw_refresh_token = generate_refresh_token()
        await self._refresh_tokens.create(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh_token),
            expires_at=refresh_token_expiry(self._settings),
        )
        return TokenResponse(access_token=access_token, refresh_token=raw_refresh_token)
