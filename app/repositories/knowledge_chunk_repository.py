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

    async def get_indexed_source_ids(self, source_type: str) -> set[uuid.UUID]:
        """해당 source_type 중 이미 색인이 있는 source_id 집합을 반환한다.

        백필 작업이 매번 전체를 다시 긁지 않고, 아직 색인 안 된(혹은 임베딩 실패로
        색인이 안 남은) 항목만 추려낼 때 쓴다.
        """
        result = await self._session.execute(
            select(KnowledgeChunk.source_id).where(KnowledgeChunk.source_type == source_type)
        )
        return set(result.scalars().all())

    async def delete_for_source(self, source_type: str, source_id: uuid.UUID) -> None:
        """원본(예: 면접 복기)이 수정/삭제될 때 낡은 색인을 지운다 (재색인 전 호출)."""
        await self._session.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.source_type == source_type,
                KnowledgeChunk.source_id == source_id,
            )
        )
