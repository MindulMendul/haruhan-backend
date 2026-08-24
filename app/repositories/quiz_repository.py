import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.quiz import Quiz
from app.db.models.quiz_question import QuizQuestion


class QuizRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        title: str,
        source_study_session_id: uuid.UUID | None,
        source_text: str | None = None,
    ) -> Quiz:
        quiz = Quiz(
            user_id=user_id,
            title=title,
            source_study_session_id=source_study_session_id,
            source_text=source_text,
        )
        self._session.add(quiz)
        await self._session.flush()
        return quiz

    async def list_for_user(self, user_id: uuid.UUID, limit: int, offset: int) -> list[Quiz]:
        result = await self._session.execute(
            select(Quiz)
            .where(Quiz.user_id == user_id)
            .order_by(Quiz.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_all_for_user(self, user_id: uuid.UUID) -> list[Quiz]:
        """페이지네이션 없이 전체를 가져온다 - 오답노트/데이터 export처럼 전량이
        필요할 때 쓴다."""
        result = await self._session.execute(
            select(Quiz).where(Quiz.user_id == user_id).order_by(Quiz.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Quiz).where(Quiz.user_id == user_id)
        )
        return result.scalar_one()

    async def get_for_user(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> Quiz | None:
        result = await self._session.execute(
            select(Quiz).where(Quiz.id == quiz_id, Quiz.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_title(self, quiz: Quiz, title: str) -> None:
        quiz.title = title
        await self._session.flush()

    async def delete(self, quiz: Quiz) -> None:
        await self._session.delete(quiz)
        await self._session.flush()


class QuizQuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        quiz_id: uuid.UUID,
        order_index: int,
        question_text: str,
        choices: list[str],
        correct_answer: str,
        explanation: str,
    ) -> QuizQuestion:
        question = QuizQuestion(
            quiz_id=quiz_id,
            order_index=order_index,
            question_text=question_text,
            choices=choices,
            correct_answer=correct_answer,
            explanation=explanation,
        )
        self._session.add(question)
        await self._session.flush()
        return question

    async def list_for_quiz(self, quiz_id: uuid.UUID) -> list[QuizQuestion]:
        result = await self._session.execute(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id == quiz_id)
            .order_by(QuizQuestion.order_index)
        )
        return list(result.scalars().all())

    async def list_for_quizzes(self, quiz_ids: list[uuid.UUID]) -> list[QuizQuestion]:
        """여러 퀴즈의 문항을 한 번에 가져온다 (데이터 export처럼 퀴즈마다
        따로 조회하면 퀴즈 개수만큼 쿼리가 느는 N+1을 피하려는 용도). 정렬은
        quiz_id, order_index 순이라 호출부에서 quiz_id별로 묶기만 하면 각
        그룹 내부도 원래 순서가 유지된다."""
        if not quiz_ids:
            return []
        result = await self._session.execute(
            select(QuizQuestion)
            .where(QuizQuestion.quiz_id.in_(quiz_ids))
            .order_by(QuizQuestion.quiz_id, QuizQuestion.order_index)
        )
        return list(result.scalars().all())
