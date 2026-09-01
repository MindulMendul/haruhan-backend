import asyncio
import json

from sqlalchemy import event

from app.core.config import get_settings
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.repositories.user_repository import UserRepository
from app.services.interview_practice_service import InterviewPracticeService
from app.services.rag_service import RagService


class FakeOllamaService:
    async def generate(self, prompt, model):
        return "면접 질문입니다."

    async def generate_json(self, prompt, model, schema):
        return json.dumps({"feedback": "좋은 답변입니다.", "next_question": "다음 질문입니다."})

    async def chat(self, messages, model):
        return "총평 텍스트입니다."

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]


def test_deleting_interview_practice_session_forgets_all_its_rag_indexed_turns(db_session_factory):
    """study_service.delete_session과 마찬가지로, 면접연습 세션을 지우면 CASCADE로
    interview_practice_turns 로우는 사라지지만 submit_answer가 문답마다 개별
    색인해둔 knowledge_chunks는 별도 FK가 없어 함께 지워지지 않는다 - 지우지
    않으면 사용자가 지운 연습 문답이 이후 무관한 학습챗/면접연습 질문의
    그라운딩 자료로 계속 되살아난다. 답변된 턴을 2개 이상 만들어(단일 턴이
    아니라 배치 삭제 경로를 실제로 여러 source_id로 exercise하도록) 전부
    지워지는지 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            ollama = FakeOllamaService()
            rag = RagService(session=session, ollama_service=ollama, settings=settings)
            service = InterviewPracticeService(session=session, ollama_service=ollama, settings=settings, rag_service=rag)

            practice_session, _ = await service.create_session(
                user_id=user.id, topic="백엔드 개발자", model="qwen2.5:3b"
            )
            await service.submit_answer(session_id=practice_session.id, user_id=user.id, answer="첫 번째 답변")
            await service.submit_answer(session_id=practice_session.id, user_id=user.id, answer="두 번째 답변")

            chunks = KnowledgeChunkRepository(session)
            before = await chunks.list_for_user(
                user.id, embedding_model=settings.embedding_model, limit=settings.rag_max_candidate_chunks
            )
            assert len(before) == 2  # 답변된 턴 2개가 각각 색인됨

            await service.delete_session(session_id=practice_session.id, user_id=user.id)

            after = await chunks.list_for_user(
                user.id, embedding_model=settings.embedding_model, limit=settings.rag_max_candidate_chunks
            )
            assert after == []

    asyncio.run(_run())


def test_deleting_interview_practice_session_issues_a_single_batch_delete_for_rag_chunks(db_session_factory):
    """study_service의 같은 회귀 테스트와 동일한 이유 - 예전엔 delete_session이 턴
    개수만큼 forget_content(개별 DELETE+commit)를 반복 호출했다. forget_content_bulk
    로 바꾼 뒤, 답변된 턴이 여러 개여도 RAG 색인 삭제 DELETE 문이 정확히 1번만
    나가는지 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            settings = get_settings()
            user = await UserRepository(session).create_guest()
            await session.commit()

            ollama = FakeOllamaService()
            rag = RagService(session=session, ollama_service=ollama, settings=settings)
            service = InterviewPracticeService(session=session, ollama_service=ollama, settings=settings, rag_service=rag)

            practice_session, _ = await service.create_session(
                user_id=user.id, topic="백엔드 개발자", model="qwen2.5:3b"
            )
            await service.submit_answer(session_id=practice_session.id, user_id=user.id, answer="첫 번째 답변")
            await service.submit_answer(session_id=practice_session.id, user_id=user.id, answer="두 번째 답변")

            chunks = KnowledgeChunkRepository(session)
            before = await chunks.list_for_user(
                user.id, embedding_model=settings.embedding_model, limit=settings.rag_max_candidate_chunks
            )
            assert len(before) == 2

            chunk_delete_statements: list[str] = []

            def _record_delete(conn, cursor, statement, parameters, context, executemany):
                if statement.strip().upper().startswith("DELETE") and "knowledge_chunks" in statement:
                    chunk_delete_statements.append(statement)

            engine = session.bind.sync_engine
            event.listen(engine, "before_cursor_execute", _record_delete)
            try:
                await service.delete_session(session_id=practice_session.id, user_id=user.id)
            finally:
                event.remove(engine, "before_cursor_execute", _record_delete)

            # knowledge_chunks DELETE는 턴 개수와 무관하게 1번만(IN 절로 묶어서) 나가야 한다.
            assert len(chunk_delete_statements) == 1

            after = await chunks.list_for_user(
                user.id, embedding_model=settings.embedding_model, limit=settings.rag_max_candidate_chunks
            )
            assert after == []

    asyncio.run(_run())
