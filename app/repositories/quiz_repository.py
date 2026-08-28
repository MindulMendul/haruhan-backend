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
        # created_at만으로 정렬하면 값이 같은 행 사이의 순서가 SQL 표준상 정의되어
        # 있지 않다 - 페이지마다 그 순서가 달라질 수 있어서, LIMIT/OFFSET으로 나눠
        # 받으면 같은 퀴즈가 두 페이지에 다시 나오거나(중복) 어느 페이지에도 안
        # 나올(누락) 수 있다. id를 2차 정렬 기준으로 추가해 동률을 항상 같은
        # 순서로 결정론적으로 깨지도록 한다.
        result = await self._session.execute(
            select(Quiz)
            .where(Quiz.user_id == user_id)
            .order_by(Quiz.created_at.desc(), Quiz.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_all_for_user(self, user_id: uuid.UUID) -> list[Quiz]:
        """페이지네이션 없이 전체를 가져온다 - 오답노트/데이터 export처럼 전량이
        필요할 때 쓴다.

        created_at만으로 정렬하면 값이 같은 행 사이의 순서가 SQL 표준상 정의되어
        있지 않다 - list_for_user()는 이미 id를 2차 정렬 기준으로 추가했지만, 이
        메서드는 페이지네이션이 없어(중복/누락 위험은 없음) 그 수정에서 빠졌었다.
        페이지네이션 여부와 무관하게 같은 호출이 매번 같은 순서를 반환하도록
        일관되게 맞춘다(오답노트/export 결과가 호출마다 달라 보이는 걸 방지).
        """
        result = await self._session.execute(
            select(Quiz).where(Quiz.user_id == user_id).order_by(Quiz.created_at.desc(), Quiz.id.desc())
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
        재현/검증할 수 없다(같은 이유로 `interview_practice_repository.py`/
        `interview_review_repository.py`의 `get_for_user_locked()`도 이 한계를
        똑같이 갖는다).
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

    async def create_many(
        self, quiz_id: uuid.UUID, questions: list[tuple[str, list[str], str, str]]
    ) -> None:
        """create()의 배치 버전 - AI가 만든 문항을 하나씩 저장할 때마다 개별
        flush()(=DB 왕복)하는 대신 add_all() + flush() 한 번으로 처리한다.
        문항 수만큼(최대 max_quiz_question_count) 반복되는 개별 왕복은 이미
        Ollama 호출을 거친 뒤에 이어지는 구간이라 사용자 체감 지연에 그대로
        얹힌다. order_index는 questions 리스트 순서 그대로(0부터) 부여된다 -
        저장된 QuizQuestion 객체가 이후에 필요 없는 호출부(반환값 없음)에서만
        쓸 수 있다.

        questions의 각 항목은 (question_text, choices, correct_answer, explanation)
        4개 튜플이다.
        """
        session_questions = [
            QuizQuestion(
                quiz_id=quiz_id,
                order_index=index,
                question_text=question_text,
                choices=choices,
                correct_answer=correct_answer,
                explanation=explanation,
            )
            for index, (question_text, choices, correct_answer, explanation) in enumerate(questions)
        ]
        self._session.add_all(session_questions)
        await self._session.flush()

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
