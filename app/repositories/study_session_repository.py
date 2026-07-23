import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.db.models.study_session import StudySession


class StudySessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID, title: str, model: str) -> StudySession:
        study_session = StudySession(user_id=user_id, title=title, model=model)
        self._session.add(study_session)
        await self._session.flush()
        return study_session

    async def list_for_user(self, user_id: uuid.UUID) -> list[StudySession]:
        result = await self._session.execute(
            select(StudySession)
            .where(StudySession.user_id == user_id)
            .order_by(StudySession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> StudySession | None:
        result = await self._session.execute(
            select(StudySession).where(StudySession.id == session_id, StudySession.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, study_session: StudySession) -> None:
        await self._session.delete(study_session)
        await self._session.flush()

    async def touch(self, study_session: StudySession) -> None:
        """새 메시지가 추가될 때 목록 정렬 순서가 최신으로 오도록 updated_at을 갱신한다.

        컬럼을 직접 건드리지 않으면 onupdate=func.now()가 발동하지 않는다
        (이 로우에 대한 UPDATE 자체가 안 나가므로).
        """
        study_session.updated_at = utcnow_naive()
        await self._session.flush()
