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
