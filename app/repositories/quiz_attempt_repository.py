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

    async def list_for_user(self, user_id: uuid.UUID) -> list[QuizAttempt]:
        """사용자의 모든 퀴즈에 걸친 전체 제출 이력 - 데이터 export용."""
        result = await self._session.execute(
            select(QuizAttempt)
            .where(QuizAttempt.user_id == user_id)
            .order_by(QuizAttempt.submitted_at)
        )
        return list(result.scalars().all())

    async def list_for_quiz(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> list[QuizAttempt]:
        """한 퀴즈에 대한 전체 재도전 이력 (최신순) - 점수 추이 확인용."""
        result = await self._session.execute(
            select(QuizAttempt)
            .where(QuizAttempt.quiz_id == quiz_id, QuizAttempt.user_id == user_id)
            .order_by(QuizAttempt.submitted_at.desc())
        )
        return list(result.scalars().all())


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

    async def list_for_attempts(self, attempt_ids: list[uuid.UUID]) -> list[QuizAnswer]:
        """여러 시도의 답안을 한 번에 가져온다 (데이터 export처럼 시도마다
        따로 조회하면 시도 개수만큼 쿼리가 느는 N+1을 피하려는 용도). 호출부에서
        attempt_id별로 묶어서 쓴다."""
        if not attempt_ids:
            return []
        result = await self._session.execute(
            select(QuizAnswer).where(QuizAnswer.attempt_id.in_(attempt_ids)).order_by(QuizAnswer.attempt_id)
        )
        return list(result.scalars().all())
