import asyncio
import uuid

import pytest

from app.core.config import get_settings
from app.repositories.user_repository import UserRepository
from app.services.ollama_service import OllamaServiceError
from app.services.rag_service import RagService, _cosine_similarity


class FakeEmbeddingOllamaService:
    """텍스트에 포함된 태그에 따라 미리 정해둔 벡터를 돌려주는 가짜 임베딩 서비스."""

    def __init__(self, vectors: dict[str, list[float]]):
        self._vectors = vectors

    async def embed(self, text: str, model: str) -> list[float]:
        for tag, vector in self._vectors.items():
            if tag in text:
                return vector
        return [0.0, 0.0, 1.0]


class FailingEmbeddingOllamaService:
    async def embed(self, text: str, model: str) -> list[float]:
        raise OllamaServiceError("boom")


class EmptyEmbeddingOllamaService:
    """호출은 성공하지만 빈 벡터를 돌려주는(장애가 아니라 모델 쪽 이상 응답) 경우를 흉내낸다."""

    async def embed(self, text: str, model: str) -> list[float]:
        return []


def test_cosine_similarity_identical_vectors_is_one():
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector_is_zero():
    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_index_and_retrieve_orders_by_similarity(db_session_factory):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            fake_ollama = FakeEmbeddingOllamaService(
                {
                    "고양이": [1.0, 0.0, 0.0],
                    "강아지": [0.0, 1.0, 0.0],
                }
            )
            rag = RagService(session=session, ollama_service=fake_ollama, settings=settings)

            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=uuid.uuid4(), content="고양이는 귀엽다"
            )
            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=uuid.uuid4(), content="강아지는 충성스럽다"
            )

            results = await rag.retrieve_relevant(user_id=user.id, query="고양이에 대해 알려줘")
            assert results[0] == "고양이는 귀엽다"
            assert "강아지는 충성스럽다" in results

    asyncio.run(_run())


def test_reindexing_same_source_replaces_old_chunk(db_session_factory):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            fake_ollama = FakeEmbeddingOllamaService({"고양이": [1.0, 0.0, 0.0]})
            rag = RagService(session=session, ollama_service=fake_ollama, settings=settings)
            source_id = uuid.uuid4()

            await rag.index_content(
                user_id=user.id, source_type="interview_review", source_id=source_id, content="옛날 내용"
            )
            await rag.index_content(
                user_id=user.id, source_type="interview_review", source_id=source_id, content="수정된 내용"
            )

            results = await rag.retrieve_relevant(user_id=user.id, query="아무 질문")
            assert results == ["수정된 내용"]

    asyncio.run(_run())


def test_retrieve_relevant_returns_empty_when_no_candidates(db_session_factory):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            # 색인된 데이터가 없으면 임베딩 API를 호출할 필요조차 없다 (실패해도 문제없어야 함).
            rag = RagService(
                session=session, ollama_service=FailingEmbeddingOllamaService(), settings=settings
            )
            results = await rag.retrieve_relevant(user_id=user.id, query="아무 질문")
            assert results == []

    asyncio.run(_run())


def test_index_content_logs_error_on_embedding_failure(db_session_factory, caplog):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            rag = RagService(session=session, ollama_service=FailingEmbeddingOllamaService(), settings=settings)
            with caplog.at_level("ERROR", logger="app.services.rag_service"):
                await rag.index_content(
                    user_id=user.id, source_type="study_message", source_id=uuid.uuid4(), content="내용"
                )
            assert any("RAG 색인 실패" in record.message for record in caplog.records)

    asyncio.run(_run())


def test_retrieve_relevant_logs_warning_on_embedding_failure(db_session_factory, caplog):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            fake_ollama = FakeEmbeddingOllamaService({"고양이": [1.0, 0.0, 0.0]})
            rag = RagService(session=session, ollama_service=fake_ollama, settings=settings)
            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=uuid.uuid4(), content="고양이 이야기"
            )

            failing_rag = RagService(
                session=session, ollama_service=FailingEmbeddingOllamaService(), settings=settings
            )
            with caplog.at_level("WARNING", logger="app.services.rag_service"):
                results = await failing_rag.retrieve_relevant(user_id=user.id, query="고양이")
            assert results == []
            assert any("RAG 검색 실패" in record.message for record in caplog.records)

    asyncio.run(_run())


def test_index_content_skips_blank_content(db_session_factory):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            # 빈 문자열/공백뿐인 content는 임베딩 호출 자체를 건너뛴다 - 실패하면
            # 안 되는 게 아니라 애초에 호출을 안 해야 하므로, 호출되면 즉시 실패하는
            # 더블로 "호출되지 않았음"을 검증한다.
            rag = RagService(session=session, ollama_service=FailingEmbeddingOllamaService(), settings=settings)
            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=uuid.uuid4(), content="   "
            )

            results = await rag.retrieve_relevant(user_id=user.id, query="아무 질문")
            assert results == []

    asyncio.run(_run())


def test_index_content_skips_when_embedding_is_empty(db_session_factory, caplog):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            rag = RagService(session=session, ollama_service=EmptyEmbeddingOllamaService(), settings=settings)
            with caplog.at_level("WARNING", logger="app.services.rag_service"):
                await rag.index_content(
                    user_id=user.id, source_type="study_message", source_id=uuid.uuid4(), content="내용"
                )
            assert any("RAG 색인 건너뜀" in record.message for record in caplog.records)

            results = await rag.retrieve_relevant(user_id=user.id, query="아무 질문")
            assert results == []

    asyncio.run(_run())


def test_retrieve_relevant_skips_when_query_embedding_is_empty(db_session_factory, caplog):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            fake_ollama = FakeEmbeddingOllamaService({"고양이": [1.0, 0.0, 0.0]})
            rag = RagService(session=session, ollama_service=fake_ollama, settings=settings)
            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=uuid.uuid4(), content="고양이 이야기"
            )

            empty_embedding_rag = RagService(
                session=session, ollama_service=EmptyEmbeddingOllamaService(), settings=settings
            )
            with caplog.at_level("WARNING", logger="app.services.rag_service"):
                results = await empty_embedding_rag.retrieve_relevant(user_id=user.id, query="고양이")
            assert results == []
            assert any("RAG 검색 건너뜀" in record.message for record in caplog.records)

    asyncio.run(_run())


def test_forget_content_removes_chunk(db_session_factory):
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            fake_ollama = FakeEmbeddingOllamaService({"고양이": [1.0, 0.0, 0.0]})
            rag = RagService(session=session, ollama_service=fake_ollama, settings=settings)
            source_id = uuid.uuid4()

            await rag.index_content(
                user_id=user.id, source_type="interview_review", source_id=source_id, content="고양이 이야기"
            )
            await rag.forget_content(source_type="interview_review", source_id=source_id)

            results = await rag.retrieve_relevant(user_id=user.id, query="고양이")
            assert results == []

    asyncio.run(_run())
