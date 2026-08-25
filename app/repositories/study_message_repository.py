import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.study_message import StudyMessage


class StudyMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, session_id: uuid.UUID, role: str, content: str) -> StudyMessage:
        message = StudyMessage(session_id=session_id, role=role, content=content)
        self._session.add(message)
        await self._session.flush()
        return message

    async def list_for_session(self, session_id: uuid.UUID) -> list[StudyMessage]:
        """created_at만으로 정렬하면 값이 같은 행(같은 요청 안에서 몇 ms 사이에
        만들어지는 user/assistant 메시지 쌍 등) 사이의 순서가 SQL 표준상 정의돼
        있지 않다 - id를 2차 정렬 기준으로 추가해 동률을 항상 같은 순서로
        결정론적으로 깨지도록 한다(list_recent_for_session과 같은 이유이자
        같은 상대 순서 - id 오름차순 - 를 쓴다)."""
        result = await self._session.execute(
            select(StudyMessage)
            .where(StudyMessage.session_id == session_id)
            .order_by(StudyMessage.created_at, StudyMessage.id)
        )
        return list(result.scalars().all())

    async def list_recent_for_session(self, session_id: uuid.UUID, limit: int) -> list[StudyMessage]:
        """채팅 프롬프트에 포함할 최근 대화만 가져온다.

        예전엔 send_message/stream_message가 이 세션의 전체 히스토리를
        list_for_session()으로 가져온 뒤 파이썬에서 뒤쪽 N개만 잘랐다 - 세션
        메시지 수엔 제한이 없어 대화가 길어질수록(오래 쓸수록) 매 턴마다 이미
        안 쓸 앞부분까지 통째로 DB에서 읽어오는 낭비가 계속 커졌다. `ORDER BY
        DESC LIMIT`으로 필요한 만큼만 가져온 뒤, 프롬프트에 넣기 좋게 다시
        시간순으로 뒤집는다.

        limit이 0 이하면 빈 리스트를 반환한다 - SQL `LIMIT`은 음수를 그대로
        받으면 방언마다 다르게 취급되므로(예: SQLite는 "제한 없음"으로 해석),
        호출 전에 명시적으로 처리해야 한다(파이썬 슬라이싱의 `history[-0:]`이
        빈 리스트가 아니라 전체 리스트가 되어버리는 것과 같은 종류의 함정).

        created_at만으로 정렬하면 값이 같은 행(같은 요청 안에서 몇 ms 사이에
        만들어지는 user/assistant 메시지 쌍 등) 사이의 순서가 SQL 표준상
        정의돼 있지 않다 - LIMIT으로 자르면 동률 그룹의 어느 쪽이 잘려나갈지가
        방언/실행마다 달라질 수 있다. id를 2차 정렬 기준으로 추가해 동률을
        항상 같은 순서로 결정론적으로 깨지도록 한다(다른 리포지토리들의
        list_for_user와 같은 이유).
        """
        if limit <= 0:
            return []
        result = await self._session.execute(
            select(StudyMessage)
            .where(StudyMessage.session_id == session_id)
            .order_by(StudyMessage.created_at.desc(), StudyMessage.id.desc())
            .limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def list_for_sessions(self, session_ids: list[uuid.UUID]) -> list[StudyMessage]:
        """여러 세션의 메시지를 한 번에 가져온다 (데이터 export처럼 세션마다
        따로 조회하면 세션 개수만큼 쿼리가 느는 N+1을 피하려는 용도).
        정렬은 session_id, created_at, id 순이라 호출부에서 session_id별로
        묶기만 하면 각 그룹 내부도 시간순(동률은 id로 결정론적으로 깨짐)이
        유지된다."""
        if not session_ids:
            return []
        result = await self._session.execute(
            select(StudyMessage)
            .where(StudyMessage.session_id.in_(session_ids))
            .order_by(StudyMessage.session_id, StudyMessage.created_at, StudyMessage.id)
        )
        return list(result.scalars().all())
