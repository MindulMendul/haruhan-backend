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

    async def get_for_user_locked(self, quiz_id: uuid.UUID, user_id: uuid.UUID) -> Quiz | None:
        """get_for_user()와 같지만 `SELECT ... FOR UPDATE`로 이 퀴즈 행을 잠근다.

        submit_answers()는 "최근 5초 안에 완전히 같은 답안 제출이 있었는지"를
        확인한 뒤에야 새 QuizAttempt를 만드는 check-then-act다 - 네트워크 재시도나
        이중 클릭으로 같은 답안이 거의 동시에 두 번 제출되면, 서로 다른 트랜잭션인
        두 요청이 둘 다 "최근 제출 없음"을 보고 통과해서 각자 QuizAttempt를 만들 수
        있다(중복 방지 로직이 막으려던 상황을 그대로 허용). 이 조회로 같은 퀴즈+
        사용자에 대한 제출을 직렬화하면, 먼저 도착한 요청이 커밋을 마칠 때까지
        나중 요청이 이 SELECT에서 대기했다가 그제야 (이미 커밋된) 직전 제출을
        보게 되어 중복 감지가 정상 동작한다. Postgres(운영)에서만 실제로 잠그고,
        SQLite(테스트/로컬)는 FOR UPDATE를 지원하지 않아 이 조회가 일반 SELECT로
        컴파일된다 - 그래서 이 잠금에 의존하는 동시성 자체는 SQLite 기반 테스트로
        재현/검증할 수 없다(54번 라운드에서 이미 마주친 것과 같은 성격의 한계).
        """
        result = await self._session.execute(
            select(Quiz).where(Quiz.id == quiz_id, Quiz.user_id == user_id).with_for_update()
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
