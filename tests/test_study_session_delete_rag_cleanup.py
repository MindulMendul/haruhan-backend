import asyncio

from sqlalchemy import event

from app.core.config import get_settings
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.repositories.user_repository import UserRepository
from app.services.rag_service import RagService
from app.services.study_service import StudyService


class FakeOllamaService:
    async def chat(self, messages, model):
        return "assistant reply"

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]


def test_deleting_study_session_forgets_its_rag_indexed_messages(db_session_factory):
    """세션을 지우면 CASCADE로 study_messages 로우는 사라지지만, 그 메시지들이
    send_message에서 개별적으로 RAG 색인해둔 knowledge_chunks는 별도 FK가 없어
    함께 지워지지 않는다 - 지우지 않으면 사용자가 삭제한 대화 내용이 이후
    무관한 학습챗 질문의 그라운딩 자료로 계속 되살아난다. delete_session이
    interview_practice_service.delete_session과 같은 방식으로 메시지 id를
    먼저 모아 forget_content를 호출하는지 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            ollama = FakeOllamaService()
            rag = RagService(session=session, ollama_service=ollama, settings=settings)
            study_service = StudyService(
                session=session, ollama_service=ollama, rag_service=rag, settings=settings
            )

            study_session = await study_service.create_session(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            await study_service.send_message(
                session_id=study_session.id, user_id=user.id, content="지울 대화 내용"
            )

            chunks = KnowledgeChunkRepository(session)
            before = await chunks.list_for_user(
                user.id, embedding_model=settings.embedding_model, limit=settings.rag_max_candidate_chunks
            )
            assert len(before) == 2  # user + assistant message 각각 색인됨

            await study_service.delete_session(session_id=study_session.id, user_id=user.id)

            after = await chunks.list_for_user(
                user.id, embedding_model=settings.embedding_model, limit=settings.rag_max_candidate_chunks
            )
            assert after == []

    asyncio.run(_run())


def test_deleting_study_session_issues_a_single_batch_delete_for_rag_chunks(db_session_factory):
    """예전엔 delete_session이 메시지 id를 모은 뒤 forget_content(개별 DELETE+commit)를
    메시지 개수만큼 반복 호출했다 - 오래 쓴(메시지가 많이 쌓인) 세션일수록 삭제
    요청이 그만큼 느려지는 N+1 쓰기였다. forget_content_bulk로 바꾼 뒤, 메시지가
    여러 개(대화 2번 = 4개 청크)여도 RAG 색인 삭제 DELETE 문이 정확히 1번만
    나가는지 SQLAlchemy의 before_cursor_execute 이벤트로 직접 세어서 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            ollama = FakeOllamaService()
            rag = RagService(session=session, ollama_service=ollama, settings=settings)
            study_service = StudyService(
                session=session, ollama_service=ollama, rag_service=rag, settings=settings
            )

            study_session = await study_service.create_session(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            await study_service.send_message(
                session_id=study_session.id, user_id=user.id, content="첫 번째 대화"
            )
            await study_service.send_message(
                session_id=study_session.id, user_id=user.id, content="두 번째 대화"
            )

            chunks = KnowledgeChunkRepository(session)
            before = await chunks.list_for_user(
                user.id, embedding_model=settings.embedding_model, limit=settings.rag_max_candidate_chunks
            )
            assert len(before) == 4  # 대화 2번 x (user + assistant) 각각 색인됨

            chunk_delete_statements: list[str] = []

            def _record_delete(conn, cursor, statement, parameters, context, executemany):
                if statement.strip().upper().startswith("DELETE") and "knowledge_chunks" in statement:
                    chunk_delete_statements.append(statement)

            engine = session.bind.sync_engine
            event.listen(engine, "before_cursor_execute", _record_delete)
            try:
                await study_service.delete_session(session_id=study_session.id, user_id=user.id)
            finally:
                event.remove(engine, "before_cursor_execute", _record_delete)

            # knowledge_chunks DELETE는 메시지(청크) 개수와 무관하게 1번만(IN 절로 묶어서) 나가야 한다.
            assert len(chunk_delete_statements) == 1

            after = await chunks.list_for_user(
                user.id, embedding_model=settings.embedding_model, limit=settings.rag_max_candidate_chunks
            )
            assert after == []

    asyncio.run(_run())


def test_delete_for_sources_is_a_no_op_for_an_empty_source_id_list(db_session_factory):
    """RagService.forget_content_bulk가 빈 리스트를 애초에 걸러주긴 하지만(이미
    메시지/턴이 없던 세션을 지울 때 등), 리포지토리 메서드 자체도 다른
    list_for_attempts/list_for_sessions류처럼 빈 입력에서 안전한 no-op이어야
    한다 - 빈 IN절(`IN ()`)은 방언에 따라 SQL 오류를 낼 수 있다."""

    async def _run():
        async with db_session_factory() as session:
            await KnowledgeChunkRepository(session).delete_for_sources("study_message", [])
            await session.commit()

    asyncio.run(_run())
