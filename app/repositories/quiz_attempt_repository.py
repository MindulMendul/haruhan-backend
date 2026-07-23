import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.quiz_answer import QuizAnswer
from app.db.models.quiz_attempt import QuizAttempt


class QuizAttemptRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, quiz_id: uuid.UUID, user_id: uuid.UUID, score: int, total: int) -> QuizAttempt:
        attempt = QuizAttempt(quiz_id=quiz_id, user_id=user_id, score=score, total=total)
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def get_latest_for_quiz(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> QuizAttempt | None:
        result = await self._session.execute(
            select(QuizAttempt)
            .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.user_id == user_id)
            .order_by(QuizAttempt.submitted_at.desc())
        )
        return result.scalars().first()


class QuizAnswerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, attempt_id: uuid.UUID, question_id: uuid.UUID, selected_index: int, is_correct: bool
    ) -> QuizAnswer:
        answer = QuizAnswer(
            attempt_id=attempt_id,
            question_id=question_id,
            selected_index=selected_index,
            is_correct=is_correct,
        )
        self._session.add(answer)
        await self._session.flush()
        return answer

    async def list_for_attempt(self, attempt_id: uuid.UUID) -> list[QuizAnswer]:
        result = await self._session.execute(
            select(QuizAnswer).where(QuizAnswer.attempt_id == attempt_id)
        )
        return list(result.scalars().all())
