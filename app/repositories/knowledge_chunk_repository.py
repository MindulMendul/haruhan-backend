import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.knowledge_chunk import KnowledgeChunk


class KnowledgeChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        user_id: uuid.UUID,
        source_type: str,
        source_id: uuid.UUID,
        content: str,
        embedding: list[float],
        embedding_model: str,
    ) -> KnowledgeChunk:
        chunk = KnowledgeChunk(
            user_id=user_id,
            source_type=source_type,
            source_id=source_id,
            content=content,
            embedding=embedding,
            embedding_model=embedding_model,
        )
        self._session.add(chunk)
        await self._session.flush()
        return chunk

    async def list_for_user(self, user_id: uuid.UUID, embedding_model: str) -> list[KnowledgeChunk]:
        """embedding_model이 일치하는 청크만 반환한다 - 모델이 다르면 임베딩 공간이 달라
        코사인 유사도 비교 자체가 의미 없다."""
        result = await self._session.execute(
            select(KnowledgeChunk).where(
                KnowledgeChunk.user_id == user_id,
                KnowledgeChunk.embedding_model == embedding_model,
            )
        )
        return list(result.scalars().all())

    async def delete_for_source(self, source_type: str, source_id: uuid.UUID) -> None:
        """원본(예: 면접 복기)이 수정/삭제될 때 낡은 색인을 지운다 (재색인 전 호출)."""
        await self._session.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.source_type == source_type,
                KnowledgeChunk.source_id == source_id,
            )
        )
