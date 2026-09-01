import uuid
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, email: str, hashed_password: str) -> User:
        user = User(email=email, hashed_password=hashed_password)
        self._session.add(user)
        await self._session.flush()
        return user

    async def create_guest(self) -> User:
        """로그인 폼 없이 자동으로 발급되는 익명 사용자. email/hashed_password가 없다."""
        user = User(email=None, hashed_password=None)
        self._session.add(user)
        await self._session.flush()
        return user

    async def delete(self, user: User) -> None:
        """User row만 지우면 나머지(학습챗/퀴즈/면접연습/면접복기/RAG 색인/refresh
        token)는 전부 DB의 ON DELETE CASCADE로 함께 지워진다."""
        await self._session.delete(user)
        await self._session.flush()

    async def delete_stale_guests(self, now: datetime) -> int:
        """활성(미폐기, 미만료) refresh token이 하나도 남지 않은 게스트 계정을
        정리한다. 게스트는 email/password가 없어(docs/FRONTEND_INTEGRATION.md의
        "이전 데이터에는 다시 접근할 방법이 없습니다") 재로그인 자체가 불가능한
        인증 방식이다 - 유일하게 그 계정에 다시 접근할 수 있는 수단인 활성
        refresh token이 전부 만료/폐기되고 나면, 그 User row와 거기 딸린
        학습챗/퀴즈/면접연습/면접복기/RAG 색인은 본인을 포함해 아무도 다시
        접근할 방법이 없는 채로 무기한 남는다 - delete()와 마찬가지로 User row만
        지우면 나머지는 DB의 ON DELETE CASCADE로 함께 지워진다.

        email이 있는 실계정은 대상에서 제외한다(비밀번호로 언제든 재로그인
        가능하므로 세션이 전부 만료돼도 데이터가 죽지 않는다).
        """
        has_active_token = (
            select(RefreshToken.id)
            .where(
                RefreshToken.user_id == User.id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .exists()
        )
        result = await self._session.execute(delete(User).where(User.email.is_(None), ~has_active_token))
        await self._session.commit()
        # DELETE 실행 결과는 실제로 CursorResult라 rowcount가 있다 - mypy 스텁이 이 경우
        # 반환 타입을 Result[Any]로만 좁혀서 생기는 오탐이다(refresh_token_repository.py의
        # delete_expired()와 같은 이유).
        return result.rowcount  # type: ignore[attr-defined]
