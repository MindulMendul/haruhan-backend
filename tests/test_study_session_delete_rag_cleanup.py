import asyncio

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
