import asyncio
import json

from app.core.config import get_settings
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository
from app.services.quiz_service import QuizService
from app.services.rag_service import RagService

SAMPLE_QUIZ_JSON = json.dumps(
    {
        "questions": [
            {
                "question": "질문?",
                "choices": ["A", "B"],
                "correct_answer": "A",
                "explanation": "설명",
            }
        ]
    }
)


class FakeOllamaService:
    async def generate_json(self, prompt, model, schema):
        return SAMPLE_QUIZ_JSON

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]


def test_quiz_from_raw_source_text_gets_indexed_for_rag(db_session_factory):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)
            quiz_service = QuizService(session=session, ollama_service=FakeOllamaService(), rag_service=rag, settings=settings)

            quiz = await quiz_service.create_quiz(
                user_id=user.id,
                title="퀴즈",
                study_session_id=None,
                source_text="사용자가 직접 붙여넣은 학습 내용",
                question_count=1,
                model="qwen2.5:3b",
            )

            indexed = await KnowledgeChunkRepository(session).get_indexed_source_ids("quiz_source")
            assert quiz.id in indexed

    asyncio.run(_run())


def test_quiz_from_study_session_is_not_double_indexed(db_session_factory):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            await StudyMessageRepository(session).create(
                session_id=study_session.id, role="user", content="이미 색인된 학습 내용"
            )
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeOllamaService(), settings=settings)
            quiz_service = QuizService(session=session, ollama_service=FakeOllamaService(), rag_service=rag, settings=settings)

            quiz = await quiz_service.create_quiz(
                user_id=user.id,
                title="퀴즈",
                study_session_id=study_session.id,
                source_text=None,
                question_count=1,
                model="qwen2.5:3b",
            )

            chunks = KnowledgeChunkRepository(session)
            quiz_indexed = await chunks.get_indexed_source_ids("quiz_source")
            assert quiz.id not in quiz_indexed

    asyncio.run(_run())
