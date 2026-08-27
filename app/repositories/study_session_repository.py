import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.db.models.study_session import StudySession


class StudySessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: uuid.UUID, title: str, model: str) -> StudySession:
        study_session = StudySession(user_id=user_id, title=title, model=model)
        self._session.add(study_session)
        await self._session.flush()
        return study_session

    async def list_for_user(self, user_id: uuid.UUID, limit: int, offset: int) -> list[StudySession]:
        # updated_at만으로 정렬하면 값이 같은 행(같은 순간에 만들어졌거나 touch()된
        # 세션들) 사이의 순서가 SQL 표준상 정의되어 있지 않다 - 페이지마다 그 순서가
        # 달라질 수 있어서, LIMIT/OFFSET으로 나눠 받으면 같은 세션이 두 페이지에 다시
        # 나오거나(중복) 어느 페이지에도 안 나올(누락) 수 있다. id를 2차 정렬
        # 기준으로 추가해 동률을 항상 같은 순서로 결정론적으로 깨지도록 한다.
        result = await self._session.execute(
            select(StudySession)
            .where(StudySession.user_id == user_id)
            .order_by(StudySession.updated_at.desc(), StudySession.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_all_for_user(self, user_id: uuid.UUID) -> list[StudySession]:
        """페이지네이션 없이 전체를 가져온다 - 데이터 export처럼 전량이 필요할 때 쓴다.

        created_at만으로 정렬하면 값이 같은 행 사이의 순서가 SQL 표준상 정의되어
        있지 않다 - list_for_user()는 이미 id를 2차 정렬 기준으로 추가했지만, 이
        메서드는 페이지네이션이 없어(중복/누락 위험은 없음) 그 수정에서 빠졌었다.
        페이지네이션 여부와 무관하게 같은 호출이 매번 같은 순서를 반환하도록
        일관되게 맞춘다(export 결과가 호출마다 달라 보이는 걸 방지).
        """
        result = await self._session.execute(
            select(StudySession)
            .where(StudySession.user_id == user_id)
            .order_by(StudySession.created_at, StudySession.id)
        )
        return list(result.scalars().all())

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(StudySession).where(StudySession.user_id == user_id)
        )
        return result.scalar_one()

    async def get_for_user(self, session_id: uuid.UUID, user_id: uuid.UUID) -> StudySession | None:
        result = await self._session.execute(
            select(StudySession).where(StudySession.id == session_id, StudySession.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_title(self, study_session: StudySession, title: str) -> None:
        study_session.title = title
        await self._session.flush()

    async def delete(self, study_session: StudySession) -> None:
        await self._session.delete(study_session)
        await self._session.flush()

    async def touch(self, study_session: StudySession) -> None:
        """새 메시지가 추가될 때 목록 정렬 순서가 최신으로 오도록 updated_at을 갱신한다.

        컬럼을 직접 건드리지 않으면 onupdate=func.now()가 발동하지 않는다
        (이 로우에 대한 UPDATE 자체가 안 나가므로).
        """
        study_session.updated_at = utcnow_naive()
        await self._session.flush()
