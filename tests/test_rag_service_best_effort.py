import asyncio

from app.core.config import get_settings
from app.repositories.user_repository import UserRepository
from app.services.rag_service import RagService


class FakeOllamaService:
    async def embed(self, text: str, model: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class _BrokenChunkRepository:
    """색인/정리 시점의 DB 오류(예: 커넥션 드롭)를 흉내낸다 - OllamaServiceError가
    아니라 임의의 예외라, 예전 코드에서는 잡히지 않고 그대로 위로 전파됐다."""

    async def delete_for_source(self, source_type, source_id):
        raise RuntimeError("DB 커넥션이 끊겼다고 가정")

    async def delete_for_sources(self, source_type, source_ids):
        raise RuntimeError("DB 커넥션이 끊겼다고 가정")

    async def create(self, **kwargs):
        raise RuntimeError("DB 커넥션이 끊겼다고 가정")

    async def list_for_user(self, user_id, embedding_model, limit):
        raise RuntimeError("DB 커넥션이 끊겼다고 가정")


def test_index_content_swallows_unexpected_db_error_and_leaves_session_usable(db_session_factory):
    """index_content는 항상 본 기능(채팅/복기 저장 등)이 이미 커밋된 "뒤" 마지막
    단계로 호출된다 - 임베딩 호출 실패(OllamaServiceError)만 잡던 예전 코드는
    _chunks.create()/commit()의 예상 못한 DB 오류를 그대로 전파시켜, 이미 성공한
    요청을 500으로 보이게 만들 수 있었다. DB 오류를 흉내내도 예외가 새어나가지
    않고, 세션이 rollback되어 계속 정상적으로 쓸 수 있는지(rollback을 실제로
    호출했는지) 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)
            rag._chunks = _BrokenChunkRepository()

            # 예외가 새어나가지 않아야 한다.
            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=user.id, content="색인할 내용"
            )

            # 세션이 깨진 트랜잭션 상태로 남아있지 않고 이후 작업에 계속 쓸 수 있어야 한다.
            other_user = await UserRepository(session).create_guest()
            await session.commit()
            assert other_user.id is not None

    asyncio.run(_run())


def test_forget_content_swallows_unexpected_db_error(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)
            rag._chunks = _BrokenChunkRepository()

            await rag.forget_content(source_type="study_message", source_id=user.id)

            other_user = await UserRepository(session).create_guest()
            await session.commit()
            assert other_user.id is not None

    asyncio.run(_run())


def test_forget_content_bulk_swallows_unexpected_db_error(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)
            rag._chunks = _BrokenChunkRepository()

            await rag.forget_content_bulk(source_type="study_message", source_ids=[user.id])

            other_user = await UserRepository(session).create_guest()
            await session.commit()
            assert other_user.id is not None

    asyncio.run(_run())


def test_retrieve_relevant_swallows_unexpected_db_error(db_session_factory):
    """retrieve_relevant()의 docstring은 "검색 실패는 전부 빈 리스트로 처리한다"고
    약속하지만, 정작 이 메서드 자신이 첫 줄에서 부르는 list_for_user() DB 조회는
    (임베딩 호출 실패만 잡는) try/except 밖에 있어 그 약속이 안 지켜지고 있었다 -
    index_content/forget_content(_bulk)는 전부 자기 자신의 DB 오류까지 삼키는데
    이 메서드만 빠져 있어서, 학습챗/면접연습의 모든 턴마다 도는 이 "부가 기능"
    조회 하나가 예상 못한 DB 오류(커넥션 드롭 등) 한 번에 채팅 전체를
    500(REST)/비정상 종료(WS)로 만들 수 있었다. list_for_user에 DB 오류를
    흉내내도 예외가 새어나가지 않고 빈 리스트를 반환하는지, 세션이 rollback되어
    계속 정상적으로 쓸 수 있는지 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)
            rag._chunks = _BrokenChunkRepository()

            result = await rag.retrieve_relevant(user_id=user.id, query="테스트 질문")
            assert result == []

            other_user = await UserRepository(session).create_guest()
            await session.commit()
            assert other_user.id is not None

    asyncio.run(_run())
