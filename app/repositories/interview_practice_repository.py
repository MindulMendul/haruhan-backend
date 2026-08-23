import uuid

from sqlalchemy import func, select, update
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

    async def list_for_user(
        self, user_id: uuid.UUID, limit: int, offset: int
    ) -> list[InterviewPracticeSession]:
        result = await self._session.execute(
            select(InterviewPracticeSession)
            .where(InterviewPracticeSession.user_id == user_id)
            .order_by(InterviewPracticeSession.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_all_for_user(self, user_id: uuid.UUID) -> list[InterviewPracticeSession]:
        """페이지네이션 없이 전체를 가져온다 - 데이터 export처럼 전량이 필요할 때 쓴다."""
        result = await self._session.execute(
            select(InterviewPracticeSession)
            .where(InterviewPracticeSession.user_id == user_id)
            .order_by(InterviewPracticeSession.updated_at.desc())
        )
        return list(result.scalars().all())

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(InterviewPracticeSession)
            .where(InterviewPracticeSession.user_id == user_id)
        )
        return result.scalar_one()

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

    async def delete(self, practice_session: InterviewPracticeSession) -> None:
        await self._session.delete(practice_session)
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

    async def mark_answered_if_pending(self, turn_id: uuid.UUID, answer: str, feedback: str) -> bool:
        """turn이 아직 답변되지 않은 상태(answer IS NULL)일 때만 answer/feedback을
        기록하는 compare-and-swap이다. 같은 질문에 거의 동시에 두 번 답변이
        제출되면(요청 재시도, 이중 클릭 등) 둘 다 "현재 턴은 미답변"이라고 읽은
        뒤 각자 AI 응답을 계산해서 쓰려고 할 수 있다 - 일반 UPDATE로 그냥
        덮어쓰면 나중에 도착한 쪽이 먼저 도착한 쪽의 답변/피드백을 조용히
        지워버린다(lost update). WHERE 절에 `answer IS NULL`을 넣어서, 이미
        누군가 먼저 기록한 뒤라면 이 UPDATE가 아무 행도 바꾸지 못하게 한다.
        영향받은 행이 있으면(=이 호출이 먼저 도착함) True, 없으면(=이미 늦음)
        False를 반환한다."""
        result = await self._session.execute(
            update(InterviewPracticeTurn)
            .where(InterviewPracticeTurn.id == turn_id, InterviewPracticeTurn.answer.is_(None))
            .values(answer=answer, feedback=feedback)
        )
        # UPDATE 실행 결과는 실제로 CursorResult라 rowcount가 있다 - mypy 스텁이 이 경우
        # 반환 타입을 CursorResult로 좁히지 못해 생기는 오탐이다.
        return result.rowcount == 1  # type: ignore[attr-defined]
