import asyncio

from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
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


class _MidQueryBrokenChunkRepository:
    """198라운드: 위 _BrokenChunkRepository는 세션에 손도 안 대고 곧바로 예외를
    던진다 - 그러면 세션이 실제 트랜잭션을 문 적이 없어서, 예전 코드의 `await
    self._session.rollback()`이 아무것도 expire시키지 않는다(롤백할 트랜잭션
    자체가 없으므로). 그래서 이 파일의 기존 테스트들은 전부 통과하면서도,
    정작 실제 커넥션 드롭(쿼리 도중 실패)이 세션에 이미 로드된 "이 메서드와
    무관한" 다른 객체까지 expire시켜 MissingGreenlet을 유발하는 이 라운드의
    버그는 하나도 못 잡았다. 실제로 세션에 쿼리 한 번(SELECT 1)을 먼저 날려
    진짜 트랜잭션을 연 뒤에 실패해, 파일 기반 SQLite로 재현한 것과 같은
    "쿼리 도중 커넥션이 끊기는" 상황을 흉내낸다."""

    def __init__(self, session):
        self._session = session

    async def delete_for_source(self, source_type, source_id):
        await self._session.execute(text("SELECT 1"))
        raise RuntimeError("DB 커넥션이 쿼리 도중 끊겼다고 가정")

    async def delete_for_sources(self, source_type, source_ids):
        await self._session.execute(text("SELECT 1"))
        raise RuntimeError("DB 커넥션이 쿼리 도중 끊겼다고 가정")

    async def create(self, **kwargs):
        await self._session.execute(text("SELECT 1"))
        raise RuntimeError("DB 커넥션이 쿼리 도중 끊겼다고 가정")

    async def list_for_user(self, user_id, embedding_model, limit):
        await self._session.execute(text("SELECT 1"))
        raise RuntimeError("DB 커넥션이 쿼리 도중 끊겼다고 가정")


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


def test_retrieve_relevant_does_not_expire_other_session_objects_on_db_error(db_session_factory):
    """198라운드: retrieve_relevant()의 list_for_user() 실패를 삼키는 except가
    예전엔 `await self._session.rollback()`을 불렀는데, Session.rollback()은
    expire_on_commit 설정과 무관하게 이 세션에 이미 로드된 "이 메서드와 전혀
    무관한" 다른 객체까지 전부 expire시킨다 - study_service.send_message의
    study_session처럼 호출부가 이미 로드해둔 객체가 expire되면, 그 바로 다음
    동기 속성 접근에서 MissingGreenlet으로 죽는다(위 test_ai_call_releases_db_
    connection.py의 파일 기반 SQLite 재현과 같은 매커니즘). session.rollback()
    대신 list_for_user() 하나만 SAVEPOINT(begin_nested())로 감싸도록 고쳤다 -
    이 테스트는 실제로 세션에 쿼리를 한 번 날려 진짜 트랜잭션을 연 뒤 실패하는
    _MidQueryBrokenChunkRepository로, retrieve_relevant() 호출 "전에" 이미
    로드해둔 다른 객체(user)가 실패 뒤에도 expire되지 않은 채로 남아있는지
    (sqlalchemy.inspect(user).expired) 직접 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            assert inspect(user).expired is False

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)
            rag._chunks = _MidQueryBrokenChunkRepository(session)

            result = await rag.retrieve_relevant(user_id=user.id, query="테스트 질문")
            assert result == []

            # 이 메서드와 전혀 무관하게 "호출 전에" 이미 로드돼 있던 user는
            # list_for_user()의 실패 이후에도 expire되지 않아야 한다 - 여기서
            # expired가 True면, 그 다음 user.id/user.is_guest 같은 동기 속성
            # 접근이 MissingGreenlet으로 죽는다는 뜻이다.
            assert inspect(user).expired is False

            other_user = await UserRepository(session).create_guest()
            await session.commit()
            assert other_user.id is not None

    asyncio.run(_run())


def test_index_content_does_not_expire_other_session_objects_on_db_error(db_session_factory):
    """198라운드: index_content()가 delete_for_source()/_chunks.create()의 실패를
    SAVEPOINT로 감싸지 않고 통째로 rollback()하면, 이 메서드는 항상 호출부가 본
    기능(예: study_service.send_message의 assistant_message)을 이미 커밋한 뒤에
    불리므로, 그 이미 로드된 객체까지 expire시켜버린다 - 위 retrieve_relevant()
    테스트와 같은 이유로, "호출 전에" 로드해둔 user가 실패 뒤에도 expire되지
    않은 채 남아있는지 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)
            rag._chunks = _MidQueryBrokenChunkRepository(session)

            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=user.id, content="색인할 내용"
            )

            assert inspect(user).expired is False

            other_user = await UserRepository(session).create_guest()
            await session.commit()
            assert other_user.id is not None

    asyncio.run(_run())


def test_forget_content_does_not_expire_other_session_objects_on_db_error(db_session_factory):
    """198라운드: forget_content()도 index_content()와 같은 이유로 SAVEPOINT로
    고쳤다 - "호출 전에" 로드해둔 user가 delete_for_source() 실패 뒤에도
    expire되지 않은 채 남아있는지 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)
            rag._chunks = _MidQueryBrokenChunkRepository(session)

            await rag.forget_content(source_type="study_message", source_id=user.id)

            assert inspect(user).expired is False

            other_user = await UserRepository(session).create_guest()
            await session.commit()
            assert other_user.id is not None

    asyncio.run(_run())


def test_forget_content_bulk_does_not_expire_other_session_objects_on_db_error(db_session_factory):
    """198라운드: forget_content_bulk()도 같은 이유로 SAVEPOINT로 고쳤다 - "호출
    전에" 로드해둔 user가 delete_for_sources() 실패 뒤에도 expire되지 않은 채
    남아있는지 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)
            rag._chunks = _MidQueryBrokenChunkRepository(session)

            await rag.forget_content_bulk(source_type="study_message", source_ids=[user.id])

            assert inspect(user).expired is False

            other_user = await UserRepository(session).create_guest()
            await session.commit()
            assert other_user.id is not None

    asyncio.run(_run())


def test_index_content_swallows_create_failure_without_expiring_objects(db_session_factory, monkeypatch):
    """198라운드: delete_for_source()는 성공하고 그 뒤 _chunks.create()(색인 INSERT)만
    실패하는 경우 - 위 delete_for_source() 실패 테스트와 달리, index_content()의
    두 번째 SAVEPOINT(_chunks.create() 주변)가 실제로 실행되는 경로를 커버한다.
    create()가 실패해도 "호출 전에" 로드해둔 user가 expire되지 않아야 한다."""

    async def _broken_create(self, **kwargs):
        await self._session.execute(text("SELECT 1"))
        raise RuntimeError("색인 생성 도중 DB 오류가 났다고 가정")

    monkeypatch.setattr(KnowledgeChunkRepository, "create", _broken_create)

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)

            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=user.id, content="색인할 내용"
            )

            assert inspect(user).expired is False

            other_user = await UserRepository(session).create_guest()
            await session.commit()
            assert other_user.id is not None

    asyncio.run(_run())


def test_safe_commit_swallows_commit_failure_and_leaves_session_usable(db_session_factory, monkeypatch):
    """198라운드: _safe_commit()이 다루는 잔여 위험 - list_for_user/delete_for_source/
    _chunks.create처럼 "쿼리 자체가 실패하는" 경우는 위 테스트들처럼 SAVEPOINT로
    막지만, commit() 자체가 실패하는 경우는 SAVEPOINT로 막을 수 없어(그쪽
    docstring 참고) session.rollback()으로 실제로 되돌린다 - 그래도 예외가 새어
    나가지 않고 세션이 계속 쓸 수 있는 상태로 남는지 확인한다. commit()을 첫
    호출에서만 실패하게 몽키패치해(그 이후 호출은 원래 동작으로 복원) index_
    content()의 "빈 콘텐츠" 분기가 부르는 _safe_commit() 하나만 실패를 겪게
    만든다."""

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            original_commit = session.commit
            state = {"should_fail": True}

            async def _flaky_commit():
                if state["should_fail"]:
                    state["should_fail"] = False
                    raise RuntimeError("commit 자체가 실패했다고 가정")
                return await original_commit()

            monkeypatch.setattr(session, "commit", _flaky_commit)

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)

            # content=""(공백) 분기는 delete_for_source() 직후 바로 _safe_commit()을
            # 부른다 - 그 유일한 commit() 호출이 위에서 패치한 실패를 겪는다.
            await rag.index_content(user_id=user.id, source_type="study_message", source_id=user.id, content="")

            other_user = await UserRepository(session).create_guest()
            await session.commit()
            assert other_user.id is not None

    asyncio.run(_run())
