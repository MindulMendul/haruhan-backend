import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.study_message import StudyMessage


class StudyMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, session_id: uuid.UUID, role: str, content: str) -> StudyMessage:
        message = StudyMessage(session_id=session_id, role=role, content=content)
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_for_session(self, session_id: uuid.UUID) -> list[StudyMessage]:
        result = await self._session.execute(
            select(StudyMessage)
            .where(StudyMessage.session_id == session_id)
            .order_by(StudyMessage.created_at)
        )
        return list(result.scalars().all())

    async def list_for_sessions(self, session_ids: list[uuid.UUID]) -> list[StudyMessage]:
        """여러 세션의 메시지를 한 번에 가져온다 (데이터 export처럼 세션마다
        따로 조회하면 세션 개수만큼 쿼리가 느는 N+1을 피하려는 용도).
        정렬은 session_id, created_at 순이라 호출부에서 session_id별로
        묶기만 하면 각 그룹 내부도 시간순이 유지된다."""
        if not session_ids:
            return []
        result = await self._session.execute(
            select(StudyMessage)
            .where(StudyMessage.session_id.in_(session_ids))
            .order_by(StudyMessage.session_id, StudyMessage.created_at)
        )
        return list(result.scalars().all())
