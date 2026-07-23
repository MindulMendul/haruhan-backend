import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.db.models.interview_practice_session import InterviewPracticeSession
from app.db.models.interview_practice_turn import InterviewPracticeTurn


class InterviewPracticeSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID, topic: str, model: str) -> InterviewPracticeSession:
        practice_session = InterviewPracticeSession(user_id=user_id, topic=topic, model=model)
        self._session.add(practice_session)
        await self._session.flush()
        return practice_session

    async def list_for_user(self, user_id: uuid.UUID) -> list[InterviewPracticeSession]:
        result = await self._session.execute(
            select(InterviewPracticeSession)
            .where(InterviewPracticeSession.user_id == user_id)
            .order_by(InterviewPracticeSession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_user(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> InterviewPracticeSession | None:
        result = await self._session.execute(
            select(InterviewPracticeSession).where(
                InterviewPracticeSession.id == session_id, InterviewPracticeSession.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def touch(self, practice_session: InterviewPracticeSession) -> None:
        practice_session.updated_at = utcnow_naive()
        await self._session.flush()


class InterviewPracticeTurnRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, session_id: uuid.UUID, order_index: int, question: str
    ) -> InterviewPracticeTurn:
        turn = InterviewPracticeTurn(session_id=session_id, order_index=order_index, question=question)
        self._session.add(turn)
        await self._session.flush()
        return turn

    async def list_for_session(self, session_id: uuid.UUID) -> list[InterviewPracticeTurn]:
        result = await self._session.execute(
            select(InterviewPracticeTurn)
            .where(InterviewPracticeTurn.session_id == session_id)
            .order_by(InterviewPracticeTurn.order_index)
        )
        return list(result.scalars().all())
