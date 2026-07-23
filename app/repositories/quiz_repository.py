import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.quiz import Quiz
from app.db.models.quiz_question import QuizQuestion


class QuizRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID, title: str, source_study_session_id: uuid.UUID | None) -> Quiz:
        quiz = Quiz(user_id=user_id, title=title, source_study_session_id=source_study_session_id)
        self._session.add(quiz)
        await self._session.flush()
        return quiz

    async def list_for_user(self, user_id: uuid.UUID) -> list[Quiz]:
        result = await self._session.execute(
            select(Quiz).where(Quiz.user_id == user_id).order_by(Quiz.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_for_user(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> Quiz | None:
        result = await self._session.execute(
            select(Quiz).where(Quiz.id == quiz_id, Quiz.user_id == user_id)
        )
        return result.scalar_one_or_none()


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
