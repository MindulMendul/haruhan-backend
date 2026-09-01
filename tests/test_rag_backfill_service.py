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
from app.repositories.interview_practice_repository import (
    InterviewPracticeSessionRepository,
    InterviewPracticeTurnRepository,
)
from app.repositories.interview_review_repository import InterviewReviewRepository
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository
from app.services.ollama_service import OllamaService, OllamaServiceError
from app.services.rag_backfill_service import (
    backfill_unindexed_content,
    run_scheduled_rag_backfill,
    sweep_orphaned_chunks,
)
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

            message_count, review_count, quiz_count, turn_count = await backfill_unindexed_content(session, rag, settings)
            assert message_count == 1
            assert review_count == 1
            assert quiz_count == 0
            assert turn_count == 0

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

            first = await backfill_unindexed_content(session, rag, settings)
            second = await backfill_unindexed_content(session, rag, settings)
            assert first == (1, 1, 0, 0)
            assert second == (0, 0, 0, 0)

    asyncio.run(_run())


def test_backfill_unindexed_content_caps_at_batch_size_and_warns(db_session_factory, monkeypatch, caplog):
    """Ollama 임베딩 엔드포인트가 며칠 연속 다운되면 그 기간 쌓인 미색인 행 전체가
    복구 후 첫 실행에 한꺼번에 몰릴 수 있다 - rag_backfill_batch_size로 한 번의
    실행이 재시도하는 건수에 상한을 둬서, 순차 임베딩 호출을 도는 동안 DB
    커넥션을 비정상적으로 오래 점유하지 않도록 한다. 상한보다 미색인 건이 많으면
    딱 상한만큼만 처리하고(나머지는 다음 실행에서 자동으로 다시 잡힘), 운영자가
    눈치챌 수 있도록 경고 로그를 남기는지 확인한다."""
    monkeypatch.setenv("RAG_BACKFILL_BATCH_SIZE", "2")
    get_settings.cache_clear()
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen"
            )
            for i in range(3):
                await StudyMessageRepository(session).create(
                    session_id=study_session.id, role="user", content=f"내용 {i}"
                )
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeEmbeddingOllamaService(), settings=settings)

            with caplog.at_level("WARNING", logger="app.services.rag_backfill_service"):
                message_count, *_ = await backfill_unindexed_content(session, rag, settings)

            assert message_count == 2  # 상한(2)만큼만 처리 - 미색인 3건 중 1건은 다음 실행으로 미룸
            assert "study_message" in caplog.text
            assert "상한" in caplog.text

            chunks = KnowledgeChunkRepository(session)
            indexed_messages = await chunks.get_indexed_source_ids("study_message")
            assert len(indexed_messages) == 2  # 3건 전부가 아니라 상한만큼만 실제로 색인됨

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
            failed_count, *_ = await backfill_unindexed_content(session, failing_rag, settings)
            assert failed_count == 1

            chunks = KnowledgeChunkRepository(session)
            assert message.id not in await chunks.get_indexed_source_ids("study_message")

            working_rag = RagService(
                session=session, ollama_service=FakeEmbeddingOllamaService(), settings=settings
            )
            retried_count, *_ = await backfill_unindexed_content(session, working_rag, settings)
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

            message_count, review_count, quiz_count, turn_count = await backfill_unindexed_content(session, rag, settings)
            assert message_count == 1
            assert review_count == 0
            assert quiz_count == 0
            assert turn_count == 0

            chunks = KnowledgeChunkRepository(session)
            indexed_messages = await chunks.get_indexed_source_ids("study_message")
            assert indexed_messages == already_indexed_ids | {unindexed.id}

    asyncio.run(_run())


def test_backfill_unindexed_content_recovers_pasted_quiz_source_after_failed_embedding(db_session_factory):
    """직접 붙여넣은 텍스트로 만든 퀴즈(quiz_source)는 study_message/interview_review와
    달리 원본이 quizzes.source_text 컬럼에만 있다 - 생성 시점 임베딩 호출이
    실패하면(Ollama 일시 장애 등) 이 백필이 재시도해주지 않는 한 그 텍스트는
    영영 RAG 검색 대상이 될 기회를 잃는다. source_text가 채워진 채로 아직
    색인이 없는 퀴즈(=실패 직후 상태를 그대로 재현)를 이 job이 찾아내 색인하는지,
    그리고 학습 세션에서 파생돼 source_text가 비어있는 퀴즈는 애초에 원본이
    study_message 쪽에 이미 있으므로 여기서 건드리지 않는지 확인한다."""
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            # 생성 시점 임베딩이 실패한 상태 - source_text는 남아있지만 색인은 없다.
            pasted_quiz = await QuizRepository(session).create(
                user_id=user.id,
                title="붙여넣은 퀴즈",
                source_study_session_id=None,
                source_text="사용자가 직접 붙여넣은 학습 자료 원문",
            )
            # 학습 세션에서 파생된 퀴즈는 source_text를 안 남긴다 - 원본이 이미
            # study_message 쪽에 있어서 quiz_source로 중복 색인할 필요가 없다.
            derived_quiz = await QuizRepository(session).create(
                user_id=user.id, title="세션에서 만든 퀴즈", source_study_session_id=None, source_text=None
            )
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeEmbeddingOllamaService(), settings=settings)
            message_count, review_count, quiz_count, turn_count = await backfill_unindexed_content(session, rag, settings)
            assert (message_count, review_count, turn_count) == (0, 0, 0)
            assert quiz_count == 1

            chunks = KnowledgeChunkRepository(session)
            indexed_quizzes = await chunks.get_indexed_source_ids("quiz_source")
            assert indexed_quizzes == {pasted_quiz.id}
            assert derived_quiz.id not in indexed_quizzes

    asyncio.run(_run())


def test_backfill_unindexed_content_recovers_interview_practice_turn_after_failed_embedding(db_session_factory):
    """면접연습 문답(interview_practice_turn)도 study_message/interview_review와
    같은 방식으로 답변 제출 시점에 동기 색인되는데, 이 백필 job에는 원래 빠져
    있었다 - 답변은 interview_practice_turns 테이블에 영구 보존되니 데이터
    유실은 아니지만, 임베딩이 일시 실패하면 재시도할 방법이 없었다. 답변이
    채워진 채로 색인이 없는 턴(=실패 직후 상태)은 찾아내고, 아직 답변 안 한
    턴(=애초에 색인 대상이 아님)은 건드리지 않는지 확인한다."""
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            practice_session = await InterviewPracticeSessionRepository(session).create(
                user_id=user.id, topic="백엔드 개발자", model="qwen2.5:3b"
            )
            turns = InterviewPracticeTurnRepository(session)
            answered_turn = await turns.create(
                session_id=practice_session.id, order_index=0, question="질문1"
            )
            await turns.mark_answered_if_pending(answered_turn.id, "답변1", "피드백1")
            unanswered_turn = await turns.create(
                session_id=practice_session.id, order_index=1, question="질문2"
            )
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeEmbeddingOllamaService(), settings=settings)
            message_count, review_count, quiz_count, turn_count = await backfill_unindexed_content(session, rag, settings)
            assert (message_count, review_count, quiz_count) == (0, 0, 0)
            assert turn_count == 1

            chunks = KnowledgeChunkRepository(session)
            indexed_turns = await chunks.get_indexed_source_ids("interview_practice_turn")
            assert indexed_turns == {answered_turn.id}
            assert unanswered_turn.id not in indexed_turns

    asyncio.run(_run())


def test_sweep_orphaned_chunks_removes_chunks_whose_source_no_longer_exists(db_session_factory):
    """`RagService.index_content()`는 원본을 이미 커밋한 "뒤"(느린 임베딩 호출을
    거쳐) 색인을 만든다 - 그 사이 다른 요청이 원본을 지우면(퀴즈/학습 세션/
    면접복기/면접연습 전부 잠금 없는 조회 뒤 delete), 삭제 쪽의 forget_content()
    는 그 시점엔 아직 없는 색인을 찾다가 조용히 아무 일도 안 하고, 뒤늦게 끝난
    index_content()가 이미 지워진 원본을 가리키는 색인을 새로 만들어버린다 -
    KnowledgeChunk.source_id는 폴리모픽 참조라 FK로도 못 막는다(131라운드가
    발견했지만 "채팅 경로에 잠금을 새로 들이는 건 위험하다"며 보류한 경쟁).
    네 가지 source_type 전부에서, 원본이 없는 채로 남은 색인을 이 함수가
    찾아 지우는지 확인한다."""
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            chunks = KnowledgeChunkRepository(session)
            orphan_ids = {}
            for source_type in (
                "study_message",
                "interview_review",
                "quiz_source",
                "interview_practice_turn",
            ):
                # 원본이 이미 지워진 뒤 뒤늦게 색인이 만들어진 상황을 그대로
                # 재현한다 - 존재하지 않는 source_id를 가리키는 색인만 직접 만든다.
                orphan = await chunks.create(
                    user_id=user.id,
                    source_type=source_type,
                    source_id=uuid.uuid4(),
                    content="원본이 사라진 내용",
                    embedding=[1.0, 0.0, 0.0],
                    embedding_model=settings.embedding_model,
                )
                orphan_ids[source_type] = orphan.id
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeEmbeddingOllamaService(), settings=settings)
            removed = await sweep_orphaned_chunks(session, rag, settings)
            await session.commit()

            assert removed == 4
            remaining = await chunks.list_for_user(
                user.id, embedding_model=settings.embedding_model, limit=100
            )
            assert remaining == []

    asyncio.run(_run())


def test_sweep_orphaned_chunks_keeps_chunks_whose_source_still_exists(db_session_factory):
    """원본이 아직 살아있는 정상 색인까지 지워버리면 RAG 검색 자체가 무력화된다 -
    거짓 양성이 없는지 확인한다."""
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen"
            )
            message = await StudyMessageRepository(session).create(
                session_id=study_session.id, role="user", content="아직 살아있는 메시지"
            )
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeEmbeddingOllamaService(), settings=settings)
            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=message.id, content=message.content
            )

            removed = await sweep_orphaned_chunks(session, rag, settings)
            await session.commit()

            assert removed == 0
            chunks = KnowledgeChunkRepository(session)
            indexed = await chunks.get_indexed_source_ids("study_message")
            assert indexed == {message.id}

    asyncio.run(_run())


def test_sweep_orphaned_chunks_cleans_up_after_index_content_races_with_delete(db_session_factory):
    """위 두 테스트가 sweep_orphaned_chunks 자체를 직접 검증한다면, 이 테스트는
    그 함수가 지우는 고아 색인이 실제로 이 경쟁(원본 커밋 → 느린 임베딩 호출
    도중 다른 요청이 원본을 지움 → 뒤늦게 색인 생성)에서 나온다는 것 자체를
    end-to-end로 재현한다 - 가짜 Ollama의 embed()가 반환하기 "직전"에 별도
    세션에서 방금 만든 퀴즈를 완전히 지우도록 만들어 이 타이밍을 결정적으로
    재현한다(143라운드 계열이 확립한 기법과 동일)."""
    from app.services.quiz_service import QuizService

    settings = get_settings()

    async def _run():
        async with db_session_factory() as session_a:
            user = await UserRepository(session_a).create_guest()
            await session_a.commit()
            user_id = user.id
            quiz_holder: dict[str, uuid.UUID] = {}

            class RacingOllamaService:
                async def generate_json(self, prompt, model, schema):
                    import json as _json

                    return _json.dumps(
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

                async def embed(self, text, model):
                    async with db_session_factory() as session_b:
                        rag_b = RagService(session=session_b, ollama_service=None, settings=settings)
                        service_b = QuizService(
                            session=session_b, ollama_service=None, rag_service=rag_b, settings=settings
                        )
                        await service_b.delete_quiz(quiz_holder["id"], user_id)
                    return [1.0, 0.0, 0.0]

            ollama = RacingOllamaService()
            rag = RagService(session=session_a, ollama_service=ollama, settings=settings)
            service = QuizService(session=session_a, ollama_service=ollama, rag_service=rag, settings=settings)

            original_create = type(service._quizzes).create

            async def _capturing_create(self, *args, **kwargs):
                quiz = await original_create(self, *args, **kwargs)
                quiz_holder["id"] = quiz.id
                return quiz

            type(service._quizzes).create = _capturing_create
            try:
                quiz = await service.create_quiz(
                    user_id=user_id,
                    title="퀴즈",
                    study_session_id=None,
                    source_text="직접 붙여넣은 소스",
                    question_count=1,
                    model="qwen2.5:3b",
                )
            finally:
                type(service._quizzes).create = original_create

            still_exists = await QuizRepository(session_a).get_for_user(quiz.id, user_id)
            assert still_exists is None  # 경쟁하는 동안 실제로 지워졌다

            chunks = KnowledgeChunkRepository(session_a)
            before = await chunks.list_for_user(user_id, embedding_model=settings.embedding_model, limit=100)
            assert [c.source_id for c in before] == [quiz.id]  # 지워진 퀴즈를 가리키는 고아 색인

            removed = await sweep_orphaned_chunks(session_a, rag, settings)
            await session_a.commit()
            assert removed == 1

            after = await chunks.list_for_user(user_id, embedding_model=settings.embedding_model, limit=100)
            assert after == []

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
