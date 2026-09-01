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

    async def list_for_user(
        self, user_id: uuid.UUID, embedding_model: str, limit: int
    ) -> list[KnowledgeChunk]:
        """embedding_model이 일치하는 청크만 반환한다 - 모델이 다르면 임베딩 공간이 달라
        코사인 유사도 비교 자체가 의미 없다.

        색인된 청크는 만료/정리 로직이 없어 계정이 오래될수록 계속 쌓이기만
        한다 - limit은 그 무제한 증가에 대한 안전장치로, 최근 것부터 최대
        이 개수만큼만 코사인 유사도 채점 후보로 가져온다(RagService.
        rag_max_candidate_chunks 참고 - 정상적인 사용량에서는 사실상 영향이
        없는 넉넉한 기본값이다). created_at만으로 정렬하면 값이 같은 행
        사이의 순서가 정의돼 있지 않으므로, 잘림 경계가 매번 흔들리지 않도록
        id를 2차 정렬 기준으로 추가한다.
        """
        result = await self._session.execute(
            select(KnowledgeChunk)
            .where(
                KnowledgeChunk.user_id == user_id,
                KnowledgeChunk.embedding_model == embedding_model,
            )
            .order_by(KnowledgeChunk.created_at.desc(), KnowledgeChunk.id.desc())
            .limit(limit)
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

    async def delete_for_sources(self, source_type: str, source_ids: list[uuid.UUID]) -> None:
        """delete_for_source의 배치 버전 - 학습챗/면접연습 세션을 지울 때, 그 세션에
        속한 메시지/턴 개수만큼 개별 DELETE(+커밋)를 반복하면 오래 쓴(메시지가
        많이 쌓인) 세션일수록 요청이 느려진다. source_id 목록을 한 번에 IN 절로
        지운다."""
        if not source_ids:
            return
        await self._session.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.source_type == source_type,
                KnowledgeChunk.source_id.in_(source_ids),
            )
        )
