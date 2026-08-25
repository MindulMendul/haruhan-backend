import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.db.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID, token_hash: str, expires_at: datetime) -> RefreshToken:
        token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(token)
        await self._session.flush()
        return token

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        return result.scalar_one_or_none()

    async def list_active_for_user(
        self, user_id: uuid.UUID, limit: int, offset: int
    ) -> list[RefreshToken]:
        """로그인할 때마다 새 refresh token이 발급되고 명시적으로 로그아웃하지
        않는 한 폐기되지 않는다(여러 기기 동시 로그인을 지원하기 위한 설계) -
        같은 계정으로 반복 로그인하면(자동화된 스크립트든 잦은 재로그인이든)
        `refresh_token_expire_days`(기본 14일) 동안은 활성 세션이 계속
        쌓인다. list_quizzes 등 다른 목록 API와 동일하게 limit/offset을 받는다.

        created_at만으로 정렬하면 값이 같은 행 사이의 순서가 SQL 표준상
        정의돼 있지 않다 - id를 2차 정렬 기준으로 추가해 페이지 경계가
        흔들리지 않게 한다.
        """
        now = utcnow_naive()
        result = await self._session.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
            .order_by(RefreshToken.created_at.desc(), RefreshToken.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_active_for_user(self, user_id: uuid.UUID) -> int:
        now = utcnow_naive()
        result = await self._session.execute(
            select(func.count())
            .select_from(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )
        return result.scalar_one()

    async def get_active_by_id_for_user(self, token_id: uuid.UUID, user_id: uuid.UUID) -> RefreshToken | None:
        now = utcnow_naive()
        result = await self._session.execute(
            select(RefreshToken).where(
                RefreshToken.id == token_id,
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        token.revoked_at = utcnow_naive()
        await self._session.flush()

    async def revoke_if_active(self, token_id: uuid.UUID) -> bool:
        """아직 폐기되지 않은 경우에만 폐기한다(compare-and-swap). 호출자가
        "아직 안 폐기됨"을 확인한 뒤 이 메서드를 부르기까지도 시간차가 있어서,
        같은 토큰으로 거의 동시에 온 두 요청이 둘 다 그 확인을 통과해버릴 수
        있다 - `WHERE revoked_at IS NULL`을 건 원자적 UPDATE라 그 중 하나만
        실제로 폐기에 성공(rowcount=1)하고, 나머지는 0건으로 실패를 돌려받는다."""
        result = await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.id == token_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow_naive())
        )
        await self._session.flush()
        return result.rowcount == 1  # type: ignore[attr-defined]

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        """이미 폐기된 토큰이 재사용되면(탈취 의심) 해당 유저의 살아있는 토큰을
        전부 끊어서 공격자와 정상 사용자 모두 강제 로그아웃시킨다."""
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utcnow_naive())
        )
        await self._session.flush()

    async def delete_expired(self) -> int:
        """만료된 토큰을 정리한다. 폐기 여부와 무관하게 expires_at이 지난 건 전부 지운다 -
        이미 재사용 불가능한 상태라 남겨둘 이유가 없다."""
        result = await self._session.execute(delete(RefreshToken).where(RefreshToken.expires_at < utcnow_naive()))
        await self._session.commit()
        # DELETE 실행 결과는 실제로 CursorResult라 rowcount가 있다 - mypy 스텁이 이 경우
        # 반환 타입을 Result[Any]로만 좁혀서 생기는 오탐이다.
        return result.rowcount  # type: ignore[attr-defined]
