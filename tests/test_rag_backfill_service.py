import asyncio
import uuid
from datetime import date

import pytest

from app.core.config import get_settings
from app.repositories.interview_review_repository import InterviewReviewRepository
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository
from app.services.ollama_service import OllamaServiceError
from app.services.rag_backfill_service import backfill_unindexed_content, run_scheduled_rag_backfill
from app.services.rag_service import RagService


class FakeEmbeddingOllamaService:
    async def embed(self, text: str, model: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class FailingEmbeddingOllamaService:
    async def embed(self, text: str, model: str) -> list[float]:
        raise OllamaServiceError("boom")


def test_backfill_unindexed_content_only_indexes_missing_chunks(db_session_factory):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen"
            )
            message1 = await StudyMessageRepository(session).create(
                session_id=study_session.id, role="user", content="이미 색인됨"
            )
            message2 = await StudyMessageRepository(session).create(
                session_id=study_session.id, role="user", content="아직 색인 안됨"
            )
            review = await InterviewReviewRepository(session).create(
                user_id=user.id,
                company="회사",
                position="포지션",
                interview_date=date(2026, 1, 1),
                content="복기 내용",
                model="qwen",
            )
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeEmbeddingOllamaService(), settings=settings)
            # message1만 미리 색인해둔다 - 백필 대상에서 제외되어야 한다.
            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=message1.id, content=message1.content
            )

            message_count, review_count = await backfill_unindexed_content(session, rag)
            assert message_count == 1
            assert review_count == 1

            chunks = KnowledgeChunkRepository(session)
            indexed_messages = await chunks.get_indexed_source_ids("study_message")
            indexed_reviews = await chunks.get_indexed_source_ids("interview_review")
            assert indexed_messages == {message1.id, message2.id}
            assert indexed_reviews == {review.id}

    asyncio.run(_run())


def test_backfill_unindexed_content_is_idempotent(db_session_factory):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen"
            )
            await StudyMessageRepository(session).create(
                session_id=study_session.id, role="user", content="내용"
            )
            await InterviewReviewRepository(session).create(
                user_id=user.id,
                company="회사",
                position="포지션",
                interview_date=date(2026, 1, 1),
                content="복기 내용",
                model="qwen",
            )
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeEmbeddingOllamaService(), settings=settings)

            first_message_count, first_review_count = await backfill_unindexed_content(session, rag)
            second_message_count, second_review_count = await backfill_unindexed_content(session, rag)
            assert (first_message_count, first_review_count) == (1, 1)
            assert (second_message_count, second_review_count) == (0, 0)

    asyncio.run(_run())


def test_backfill_unindexed_content_retries_previously_failed_embedding(db_session_factory):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen"
            )
            message = await StudyMessageRepository(session).create(
                session_id=study_session.id, role="user", content="내용"
            )
            await session.commit()

            failing_rag = RagService(
                session=session, ollama_service=FailingEmbeddingOllamaService(), settings=settings
            )
            # 임베딩 호출이 실패하면 knowledge_chunks에 행이 안 남으므로, 다음 백필에서
            # 다시 대상이 되어야 한다.
            failed_count, _ = await backfill_unindexed_content(session, failing_rag)
            assert failed_count == 1

            chunks = KnowledgeChunkRepository(session)
            assert message.id not in await chunks.get_indexed_source_ids("study_message")

            working_rag = RagService(
                session=session, ollama_service=FakeEmbeddingOllamaService(), settings=settings
            )
            retried_count, _ = await backfill_unindexed_content(session, working_rag)
            assert retried_count == 1
            assert message.id in await chunks.get_indexed_source_ids("study_message")

    asyncio.run(_run())


def test_run_scheduled_rag_backfill_warns_when_db_uninitialized(caplog):
    with caplog.at_level("WARNING", logger="app.services.rag_backfill_service"):
        asyncio.run(run_scheduled_rag_backfill())
    assert "DB 엔진이 초기화되지 않아" in caplog.text
