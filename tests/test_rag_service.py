import asyncio
import threading
import uuid

import pytest

from app.core.config import get_settings
from app.repositories.user_repository import UserRepository
from app.services.ollama_service import OllamaServiceError
from app.services.rag_service import RagService, _cosine_similarity
import app.services.rag_service as rag_service_module


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


def test_retrieve_relevant_scores_candidates_off_the_event_loop_thread(db_session_factory, monkeypatch):
    """색인된 청크 수는 사용자가 오래 쓸수록 계속 늘어나기만 하는데, 예전에는
    후보 전체에 대한 코사인 유사도 채점을 이벤트 루프에서 그대로(await 없이)
    돌렸다 - 후보가 많아지면 이 채점 시간만큼 같은 워커의 다른 모든 동시
    요청이 멈춘다. asyncio.to_thread로 스레드 풀에 위임했는지를, 실제
    채점(_cosine_similarity)이 이벤트 루프 스레드가 아닌 다른 스레드에서
    호출되는지로 직접 확인한다 - 시간차 기반 검증은 asyncio.sleep이 실제
    경과 시간 기준이라 이벤트 루프가 막혀 있어도 우연히 비슷한 결과가 나올
    수 있어(타이머가 이미 만료된 채로 대기 중이었을 수 있음) 신뢰할 수 없다."""
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            fake_ollama = FakeEmbeddingOllamaService({"질문": [1.0, 0.0, 0.0]})
            rag = RagService(session=session, ollama_service=fake_ollama, settings=settings)
            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=uuid.uuid4(), content="내용"
            )

            main_thread = threading.current_thread()
            scoring_threads: list[threading.Thread] = []
            original_cosine_similarity = rag_service_module._cosine_similarity

            def _tracking_cosine_similarity(a, b):
                scoring_threads.append(threading.current_thread())
                return original_cosine_similarity(a, b)

            monkeypatch.setattr(rag_service_module, "_cosine_similarity", _tracking_cosine_similarity)

            await rag.retrieve_relevant(user_id=user.id, query="질문")

            assert scoring_threads, "채점 함수가 호출되지 않음"
            assert all(t is not main_thread for t in scoring_threads)

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


def test_list_for_user_limits_to_most_recent_chunks(db_session_factory):
    """색인된 청크(학습챗 메시지/퀴즈 소스/면접복기)는 만료/정리 로직이 없어
    계정이 오래될수록 계속 쌓이기만 한다 - retrieve_relevant()가 매 채팅/면접
    연습 턴마다 그 전체를 DB에서 읽어와 코사인 유사도로 채점하던 것에 대한
    안전장치로, list_for_user()의 limit이 최근 것부터 최대 limit개만
    반환하는지 확인한다. created_at은 server_default라 짧은 시간에 여러
    청크를 만들면 값이 동률이 되기 쉬워서(94번 라운드와 같은 함정), 순서
    검증이 흔들리지 않도록 각 청크의 created_at을 명시적으로 서로 다른
    값으로 지정한다."""
    import uuid as uuid_module
    from datetime import timedelta

    from app.core.clock import utcnow_naive
    from app.db.models.knowledge_chunk import KnowledgeChunk
    from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            base = utcnow_naive()
            for i in range(5):
                session.add(
                    KnowledgeChunk(
                        id=uuid_module.uuid4(),
                        user_id=user.id,
                        source_type="study_message",
                        source_id=uuid_module.uuid4(),
                        content=f"청크 {i}",
                        embedding=[1.0, 0.0, 0.0],
                        embedding_model="nomic-embed-text",
                        created_at=base + timedelta(seconds=i),
                    )
                )
            await session.commit()

            repo = KnowledgeChunkRepository(session)
            return (
                await repo.list_for_user(user.id, embedding_model="nomic-embed-text", limit=3),
                await repo.list_for_user(user.id, embedding_model="nomic-embed-text", limit=100),
            )

    limited, unlimited = asyncio.run(_run())

    # limit=3: 가장 최근 3개(청크 4, 3, 2)만, 최신순으로.
    assert [c.content for c in limited] == ["청크 4", "청크 3", "청크 2"]
    # limit이 총 개수보다 크면 전부(5개) 반환 - 역시 최신순.
    assert [c.content for c in unlimited] == ["청크 4", "청크 3", "청크 2", "청크 1", "청크 0"]
