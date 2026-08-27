import asyncio

from app.core.config import get_settings
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.user_repository import UserRepository
from app.services.study_service import StudyService
from app.services.rag_service import RagService


def test_send_message_returns_404_when_session_deleted_during_ai_call(db_session_factory):
    """send_message()는 세션 존재를 확인한 뒤 느린 Ollama 호출을 거쳐서야
    assistant_message를 만든다 - 그 사이 다른 요청이 이 세션을 지워버리면
    (CASCADE로 방금 만든 user_message도 함께 사라짐), assistant_message
    INSERT가 이미 없어진 부모(study_sessions)를 가리키게 되어 IntegrityError로
    실패한다. 잡지 않으면 애써 받은 AI 응답을 저장도 못 하고 버리면서 처리되지
    않은 예외(500)까지 나가버린다 - 다른 "세션 없음" 케이스와 같은 404로
    변환해야 한다. 가짜 Ollama가 응답을 반환하기 "직전"에 별도 세션에서 이
    세션을 완전히 지우도록 만들어서 이 타이밍을 결정적으로 재현한다."""

    async def _run():
        async with db_session_factory() as session_a:
            user = await UserRepository(session_a).create_guest()
            await session_a.commit()

            settings = get_settings()
            session_id_holder = [None]

            class DeletingOllamaService:
                async def chat(self, messages, model):
                    async with db_session_factory() as session_b:
                        rag_b = RagService(session=session_b, ollama_service=self, settings=settings)
                        service_b = StudyService(
                            session=session_b, ollama_service=self, rag_service=rag_b, settings=settings
                        )
                        await service_b.delete_session(
                            session_id=session_id_holder[0], user_id=user.id
                        )
                    return "늦게 도착한 답변"

                async def chat_stream(self, messages, model):
                    yield "안 씀"

                async def embed(self, text, model):
                    return [1.0, 0.0, 0.0]

            ollama = DeletingOllamaService()
            rag_a = RagService(session=session_a, ollama_service=ollama, settings=settings)
            service_a = StudyService(
                session=session_a, ollama_service=ollama, rag_service=rag_a, settings=settings
            )
            study_session = await service_a.create_session(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            session_id_holder[0] = study_session.id

            try:
                await service_a.send_message(
                    session_id=study_session.id, user_id=user.id, content="사라질 세션에 보내는 메시지"
                )
                return None
            except Exception as exc:  # noqa: BLE001 - 예외 자체를 검사해야 함
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 404
    assert exc.detail == "Study session not found"


def test_send_message_returns_404_when_session_deleted_before_first_message_insert(
    db_session_factory, monkeypatch
):
    """send_message()는 get_for_user()로 세션 존재를 확인한 뒤,
    list_recent_for_session() 조회를 한 번 더 거쳐서야 user_message를 만든다 -
    이 좁은 틈에도 다른 요청이 같은 세션을 지워버리면 user_message INSERT가
    이미 없어진 부모(study_sessions)를 가리키게 되어 IntegrityError로 실패한다.
    assistant_message INSERT 시점의 경쟁(위 테스트)과 달리 이 더 이른 INSERT는
    원래 잡히지 않고 있었다 - list_recent_for_session이 끝나는 시점에 별도
    세션에서 이 세션을 지우도록 만들어서 이 좁은 타이밍을 결정적으로
    재현한다."""

    async def _run():
        async with db_session_factory() as session_a:
            user = await UserRepository(session_a).create_guest()
            await session_a.commit()

            settings = get_settings()
            session_id_holder = [None]

            class FakeOllamaService:
                async def chat(self, messages, model):
                    return "안 씀"

                async def chat_stream(self, messages, model):
                    yield "안 씀"

                async def embed(self, text, model):
                    return [1.0, 0.0, 0.0]

            ollama = FakeOllamaService()
            rag_a = RagService(session=session_a, ollama_service=ollama, settings=settings)
            service_a = StudyService(
                session=session_a, ollama_service=ollama, rag_service=rag_a, settings=settings
            )
            study_session = await service_a.create_session(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            session_id_holder[0] = study_session.id

            original_list_recent = StudyMessageRepository.list_recent_for_session

            async def _deleting_list_recent(self, session_id, limit):
                result = await original_list_recent(self, session_id, limit)
                async with db_session_factory() as session_b:
                    rag_b = RagService(session=session_b, ollama_service=ollama, settings=settings)
                    service_b = StudyService(
                        session=session_b, ollama_service=ollama, rag_service=rag_b, settings=settings
                    )
                    await service_b.delete_session(session_id=session_id_holder[0], user_id=user.id)
                return result

            monkeypatch.setattr(StudyMessageRepository, "list_recent_for_session", _deleting_list_recent)

            try:
                await service_a.send_message(
                    session_id=study_session.id, user_id=user.id, content="사라질 세션에 보내는 메시지"
                )
                return None
            except Exception as exc:  # noqa: BLE001 - 예외 자체를 검사해야 함
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 404
    assert exc.detail == "Study session not found"


def test_stream_message_returns_404_when_session_deleted_during_ai_call(db_session_factory):
    """send_message()와 같은 경쟁을 stream_message()(WebSocket 스트리밍 버전)의
    delta 스트리밍 도중에도 재현한다 - assistant_message를 만드는 지점은
    같아서 같은 IntegrityError -> 404 변환이 필요하다."""

    async def _run():
        async with db_session_factory() as session_a:
            user = await UserRepository(session_a).create_guest()
            await session_a.commit()

            settings = get_settings()
            session_id_holder = [None]

            class DeletingOllamaService:
                async def chat(self, messages, model):
                    return "안 씀"

                async def chat_stream(self, messages, model):
                    async with db_session_factory() as session_b:
                        rag_b = RagService(session=session_b, ollama_service=self, settings=settings)
                        service_b = StudyService(
                            session=session_b, ollama_service=self, rag_service=rag_b, settings=settings
                        )
                        await service_b.delete_session(
                            session_id=session_id_holder[0], user_id=user.id
                        )
                    yield "지연된 답변 조각"

                async def embed(self, text, model):
                    return [1.0, 0.0, 0.0]

            ollama = DeletingOllamaService()
            rag_a = RagService(session=session_a, ollama_service=ollama, settings=settings)
            service_a = StudyService(
                session=session_a, ollama_service=ollama, rag_service=rag_a, settings=settings
            )
            study_session = await service_a.create_session(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            session_id_holder[0] = study_session.id

            try:
                async for _event_type, _data in service_a.stream_message(
                    session_id=study_session.id, user_id=user.id, content="사라질 세션에 보내는 메시지"
                ):
                    pass
                return None
            except Exception as exc:  # noqa: BLE001 - 예외 자체를 검사해야 함
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 404
    assert exc.detail == "Study session not found"


def test_stream_message_returns_404_when_session_deleted_before_first_message_insert(
    db_session_factory, monkeypatch
):
    """send_message()의 같은 이름 테스트와 같은 경쟁을 stream_message()(WebSocket
    스트리밍 버전)의 첫 INSERT(user_message)에서도 재현한다."""

    async def _run():
        async with db_session_factory() as session_a:
            user = await UserRepository(session_a).create_guest()
            await session_a.commit()

            settings = get_settings()
            session_id_holder = [None]

            class FakeOllamaService:
                async def chat(self, messages, model):
                    return "안 씀"

                async def chat_stream(self, messages, model):
                    yield "안 씀"

                async def embed(self, text, model):
                    return [1.0, 0.0, 0.0]

            ollama = FakeOllamaService()
            rag_a = RagService(session=session_a, ollama_service=ollama, settings=settings)
            service_a = StudyService(
                session=session_a, ollama_service=ollama, rag_service=rag_a, settings=settings
            )
            study_session = await service_a.create_session(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            session_id_holder[0] = study_session.id

            original_list_recent = StudyMessageRepository.list_recent_for_session

            async def _deleting_list_recent(self, session_id, limit):
                result = await original_list_recent(self, session_id, limit)
                async with db_session_factory() as session_b:
                    rag_b = RagService(session=session_b, ollama_service=ollama, settings=settings)
                    service_b = StudyService(
                        session=session_b, ollama_service=ollama, rag_service=rag_b, settings=settings
                    )
                    await service_b.delete_session(session_id=session_id_holder[0], user_id=user.id)
                return result

            monkeypatch.setattr(StudyMessageRepository, "list_recent_for_session", _deleting_list_recent)

            try:
                async for _event_type, _data in service_a.stream_message(
                    session_id=study_session.id, user_id=user.id, content="사라질 세션에 보내는 메시지"
                ):
                    pass
                return None
            except Exception as exc:  # noqa: BLE001 - 예외 자체를 검사해야 함
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 404
    assert exc.detail == "Study session not found"
