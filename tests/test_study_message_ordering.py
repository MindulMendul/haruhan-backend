import asyncio
import uuid

from app.core.clock import utcnow_naive
from app.db.models.study_message import StudyMessage
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository


def test_create_gives_back_to_back_messages_distinct_microsecond_timestamps(db_session_factory):
    """created_at이 예전처럼 DB server_default=CURRENT_TIMESTAMP(SQLite는 초 단위)였다면,
    같은 요청 안에서 곧바로 이어지는 user/assistant 메시지 쌍이 같은 초에 만들어져
    created_at이 완전히 같아지는 게 실제로 자주 일어난다. 파이썬 쪽에서 마이크로초
    정밀도로 직접 찍도록 바꿔서, 이런 근접 생성 쌍도 실제로 구분되는 타임스탬프를
    받는지 확인한다(QuizAttempt.submitted_at과 같은 이유)."""

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            await session.commit()

            messages = StudyMessageRepository(session)
            first = await messages.create(session_id=study_session.id, role="user", content="질문")
            second = await messages.create(session_id=study_session.id, role="assistant", content="답변")
            await session.commit()

            assert first.created_at != second.created_at
            assert first.created_at < second.created_at

    asyncio.run(_run())


def test_list_for_session_preserves_creation_order_across_many_back_to_back_messages(db_session_factory):
    """실제 서비스 흐름처럼 메시지를 연달아 만든 뒤, list_for_session이 그 생성
    순서를 그대로 유지해서 돌려주는지 확인한다 - GET /study/sessions/{id}가 이
    순서를 그대로 화면에 렌더링하고, create_quiz(study_session_id 경로)도 이
    순서로 메시지를 이어붙여 퀴즈 생성 프롬프트를 만든다."""

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            await session.commit()

            messages = StudyMessageRepository(session)
            created = []
            for i in range(6):
                role = "user" if i % 2 == 0 else "assistant"
                created.append(
                    await messages.create(session_id=study_session.id, role=role, content=f"메시지 {i}")
                )
            await session.commit()

            listed = await messages.list_for_session(study_session.id)
            assert [m.id for m in listed] == [m.id for m in created]

    asyncio.run(_run())


def test_list_for_session_breaks_genuine_created_at_ties_deterministically_by_id(db_session_factory):
    """마이크로초 정밀도로도 이론상 동률이 가능하다 - created_at이 완전히 같은
    행이 있으면 id를 2차 정렬 기준으로 항상 같은(오름차순) 순서로 결정론적으로
    깨야 한다(list_recent_for_session과 같은 상대 순서)."""

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            await session.commit()

            tied_time = utcnow_naive()
            low_id = StudyMessage(
                id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
                session_id=study_session.id,
                role="user",
                content="먼저",
                created_at=tied_time,
            )
            high_id = StudyMessage(
                id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                session_id=study_session.id,
                role="assistant",
                content="나중",
                created_at=tied_time,
            )
            session.add_all([high_id, low_id])
            await session.commit()

            listed = await StudyMessageRepository(session).list_for_session(study_session.id)
            assert [m.id for m in listed] == [low_id.id, high_id.id]

    asyncio.run(_run())
