import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.services.ollama_service import OllamaService, OllamaServiceError


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class RagService:
    """사용자 본인의 기존 기록(학습챗/면접복기)을 색인하고, 새 질문과 의미적으로
    가까운 기록을 검색해 학습챗 그라운딩에 쓴다."""

    def __init__(self, session: AsyncSession, ollama_service: OllamaService, settings: Settings) -> None:
        self._session = session
        self._chunks = KnowledgeChunkRepository(session)
        self._ollama = ollama_service
        self._settings = settings

    async def index_content(
        self, user_id: uuid.UUID, source_type: str, source_id: uuid.UUID, content: str
    ) -> None:
        """레거시 데이터를 검색 대상으로 색인한다. 같은 source에 대한 기존 색인은 먼저 지운다.

        임베딩 호출이 실패해도 색인은 부가 기능이므로 조용히 건너뛴다 - 본 기능(채팅/복기
        저장)의 흐름을 막으면 안 된다.
        """
        await self._chunks.delete_for_source(source_type, source_id)

        if not content.strip():
            await self._session.commit()
            return

        model = self._settings.embedding_model
        try:
            embedding = await self._ollama.embed(text=content, model=model)
        except OllamaServiceError:
            await self._session.commit()
            return

        if embedding:
            await self._chunks.create(
                user_id=user_id,
                source_type=source_type,
                source_id=source_id,
                content=content,
                embedding=embedding,
                embedding_model=model,
            )
        await self._session.commit()

    async def retrieve_relevant(self, user_id: uuid.UUID, query: str) -> list[str]:
        """query와 의미적으로 가까운 사용자 본인의 기존 기록 상위 K개를 반환한다.

        검색 실패는 전부 빈 리스트로 처리한다 - RAG는 답변 품질을 보강하는 부가 기능이라
        실패해도 채팅 자체는 평소대로 계속되어야 한다.
        """
        model = self._settings.embedding_model
        candidates = await self._chunks.list_for_user(user_id, embedding_model=model)
        if not candidates:
            return []

        try:
            query_embedding = await self._ollama.embed(text=query, model=model)
        except OllamaServiceError:
            return []
        if not query_embedding:
            return []

        scored = [(_cosine_similarity(query_embedding, chunk.embedding), chunk) for chunk in candidates]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top_k = self._settings.rag_top_k
        return [chunk.content for _, chunk in scored[:top_k]]

    async def forget_content(self, source_type: str, source_id: uuid.UUID) -> None:
        """원본이 삭제될 때 색인도 함께 지운다."""
        await self._chunks.delete_for_source(source_type, source_id)
        await self._session.commit()
