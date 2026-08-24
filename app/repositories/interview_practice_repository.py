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
        # updated_at만으로 정렬하면 값이 같은 행 사이의 순서가 SQL 표준상 정의되어
        # 있지 않다 - 페이지마다 그 순서가 달라질 수 있어서, LIMIT/OFFSET으로 나눠
        # 받으면 같은 세션이 두 페이지에 다시 나오거나(중복) 어느 페이지에도 안
        # 나올(누락) 수 있다. id를 2차 정렬 기준으로 추가해 동률을 항상 같은
        # 순서로 결정론적으로 깨지도록 한다.
        result = await self._session.execute(
            select(InterviewPracticeSession)
            .where(InterviewPracticeSession.user_id == user_id)
            .order_by(InterviewPracticeSession.updated_at.desc(), InterviewPracticeSession.id.desc())
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

    async def get_for_user_locked(
        self, session_id: uuid.UUID, user_id: uuid.UUID
    ) -> InterviewPracticeSession | None:
        """get_for_user()와 같지만 `SELECT ... FOR UPDATE`로 이 세션 행을 잠근다.

        submit_answer()와 complete_session()은 둘 다 `status == "in_progress"`인지
        확인한 뒤(check) 느린 Ollama 호출을 거쳐서야 쓰는(act) check-then-act다 -
        이 잠금 없이는 두 요청(예: 마지막 답변 제출과 "면접 종료"를 거의 동시에
        누름)이 서로 다른 트랜잭션에서 둘 다 "아직 진행중"이라고 읽고 통과할 수
        있다. 그러면 complete_session이 먼저 커밋해 세션을 completed로 만들어도,
        이미 시작된 submit_answer가 뒤늦게 자기 턴을 응답 완료 처리하고 새 다음
        턴까지 만들어버려 - 이미 끝난 세션에 답변할 수 없는 턴 하나가 영원히
        남는(누구도 답할 수 없고 지울 방법도 없는) 데이터 정합성 문제가 생긴다.
        이 조회로 같은 세션에 대한 두 작업을 직렬화하면, 먼저 도착한 쪽이 커밋을
        마칠 때까지 나중 쪽이 대기했다가 이미 반영된 status를 보고 다시 판단한다.
        Postgres(운영)에서만 실제로 잠그고, SQLite(테스트/로컬)는 FOR UPDATE를
        지원하지 않아 이 조회가 일반 SELECT로 컴파일된다 - 그래서 이 잠금에
        의존하는 동시성 자체는 SQLite 기반 테스트로 재현/검증할 수 없다(92/101번
        라운드에서 이미 마주친 것과 같은 성격의 한계).
        """
        result = await self._session.execute(
            select(InterviewPracticeSession)
            .where(InterviewPracticeSession.id == session_id, InterviewPracticeSession.user_id == user_id)
            .with_for_update()
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

    async def list_for_sessions(self, session_ids: list[uuid.UUID]) -> list[InterviewPracticeTurn]:
        """여러 세션의 턴을 한 번에 가져온다 (데이터 export처럼 세션마다 따로
        조회하면 세션 개수만큼 쿼리가 느는 N+1을 피하려는 용도). 정렬은
        session_id, order_index 순이라 호출부에서 session_id별로 묶기만
        하면 각 그룹 내부도 원래 순서가 유지된다."""
        if not session_ids:
            return []
        result = await self._session.execute(
            select(InterviewPracticeTurn)
            .where(InterviewPracticeTurn.session_id.in_(session_ids))
            .order_by(InterviewPracticeTurn.session_id, InterviewPracticeTurn.order_index)
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
