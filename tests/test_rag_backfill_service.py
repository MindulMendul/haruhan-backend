import asyncio
import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db import session as db_session_module
from app.db.base import Base
from app.db.session import enable_sqlite_foreign_keys
from app.repositories.interview_review_repository import InterviewReviewRepository
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository
from app.services.ollama_service import OllamaService, OllamaServiceError
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


def test_backfill_unindexed_content_scales_with_unindexed_count_not_total_count(db_session_factory):
    """이 job은 매일 도는 cron인데, 이전 구현은 study_message/interview_review
    테이블 전체를 파이썬으로 읽어와서 이미 색인된 것과 대조했다 - 서비스가
    오래될수록 거의 다 색인된 상태가 되므로, 매번 전체 이력 규모의 조회가
    반복되는 셈이었다. 미리 색인해둔 메시지가 여러 개 섞여 있어도, 아직
    색인 안 된 것만 정확히 골라 처리하는지(=SQL 단에서 걸러지는지, 결과
    건수가 여전히 정확한지) 확인한다."""
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen"
            )
            rag = RagService(session=session, ollama_service=FakeEmbeddingOllamaService(), settings=settings)

            already_indexed_ids = set()
            for i in range(5):
                message = await StudyMessageRepository(session).create(
                    session_id=study_session.id, role="user", content=f"이미 색인됨 {i}"
                )
                await session.commit()
                await rag.index_content(
                    user_id=user.id,
                    source_type="study_message",
                    source_id=message.id,
                    content=message.content,
                )
                already_indexed_ids.add(message.id)

            unindexed = await StudyMessageRepository(session).create(
                session_id=study_session.id, role="user", content="아직 색인 안됨"
            )
            await session.commit()

            message_count, review_count = await backfill_unindexed_content(session, rag)
            assert message_count == 1
            assert review_count == 0

            chunks = KnowledgeChunkRepository(session)
            indexed_messages = await chunks.get_indexed_source_ids("study_message")
            assert indexed_messages == already_indexed_ids | {unindexed.id}

    asyncio.run(_run())


def test_run_scheduled_rag_backfill_warns_when_db_uninitialized(caplog):
    with caplog.at_level("WARNING", logger="app.services.rag_backfill_service"):
        asyncio.run(run_scheduled_rag_backfill())
    assert "DB 엔진이 초기화되지 않아" in caplog.text


async def _with_initialized_engine(coro_factory):
    """run_scheduled_rag_backfill()은 자체 get_db()를 통해 모듈 전역
    _session_factory를 쓰므로, 이 함수 안에서만 임시로 채워뒀다가 반드시
    되돌린다 - 다른 테스트(엔진 미초기화 케이스 포함)가 이 전역 상태에
    영향받으면 안 된다."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    enable_sqlite_foreign_keys(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    db_session_module._engine = engine
    db_session_module._session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await coro_factory(db_session_module._session_factory)
    finally:
        db_session_module._engine = None
        db_session_module._session_factory = None
        await engine.dispose()


def test_run_scheduled_rag_backfill_indexes_and_logs_counts(monkeypatch, caplog):
    async def fake_embed(self, text, model):
        return [1.0, 0.0, 0.0]

    monkeypatch.setattr(OllamaService, "embed", fake_embed)

    async def _run(session_factory):
        async with session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen"
            )
            await StudyMessageRepository(session).create(
                session_id=study_session.id, role="user", content="내용"
            )
            await session.commit()

        with caplog.at_level("INFO", logger="app.services.rag_backfill_service"):
            await run_scheduled_rag_backfill()
        assert "study_message 1건" in caplog.text
        assert "interview_review 0건" in caplog.text

    asyncio.run(_with_initialized_engine(_run))


def test_run_scheduled_rag_backfill_logs_exception_on_unexpected_error(monkeypatch, caplog):
    async def _boom(session, rag_service):
        raise ValueError("boom")

    monkeypatch.setattr("app.services.rag_backfill_service.backfill_unindexed_content", _boom)

    async def _run(session_factory):
        with caplog.at_level("ERROR", logger="app.services.rag_backfill_service"):
            await run_scheduled_rag_backfill()
        assert "[RAG 백필] 실패" in caplog.text

    asyncio.run(_with_initialized_engine(_run))
