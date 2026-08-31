import asyncio
import logging
import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.services.ollama_service import OllamaService, OllamaServiceError

logger = logging.getLogger(__name__)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _rank_top_k(
    query_embedding: list[float], candidates: list[tuple[list[float], str]], top_k: int
) -> list[str]:
    """사용자가 오래 쓸수록 색인된 청크 수는 계속 늘어나기만 하는데(만료/정리
    없음), retrieve_relevant는 매 학습챗 메시지/면접연습 턴마다 후보 전체를
    코사인 유사도로 채점한다 - 후보가 많아지면 이 채점 자체가 무시 못 할
    CPU 작업이 되는데, 예전엔 이걸 이벤트 루프에서 그대로(await 없이) 돌려서
    그 시간만큼 같은 워커의 다른 모든 동시 요청이 멈췄다. 세션/ORM 객체가
    아니라 이미 로드된 (embedding, content) 순수 데이터만 넘겨받아, 이벤트
    루프와 무관한 스레드 풀에서 계산해도 안전하게 만들었다."""
    scored = []
    for embedding, content in candidates:
        if len(embedding) != len(query_embedding):
            # list_for_user()는 embedding_model "문자열"만 같은 후보를
            # 걸러줄 뿐, 실제 벡터 길이가 같다는 보장은 아무 데도 없다 -
            # 같은 태그의 모델이 다른 차원으로 재배포되거나 EMBEDDING_MODEL
            # 설정이 기존 색인 재생성 없이 바뀌면 차원이 다른 벡터끼리
            # 섞일 수 있다. _cosine_similarity()의 zip(a, b)는 짧은 쪽에
            # 맞춰 조용히 자르는데, norm은 원래 길이 그대로 계산되므로
            # 비교 불가능한 두 벡터가 우연히 완벽한 점수(1.0)로 채점돼
            # 실제로 관련 있는 기록을 밀어내고 1등을 차지하는 것까지
            # 실제로 재현해 확인했다 - 조용히 틀린 순위를 만드는 대신
            # 비교 불가능한 후보는 채점에서 아예 제외한다.
            logger.warning(
                "RAG 검색에서 차원이 다른 임베딩 건너뜀: query_dim=%d chunk_dim=%d",
                len(query_embedding),
                len(embedding),
            )
            continue
        scored.append((_cosine_similarity(query_embedding, embedding), content))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [content for _, content in scored[:top_k]]


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

        색인은 부가 기능이라 어떤 이유로든(임베딩 호출 실패뿐 아니라 DB 오류까지) 실패해도
        조용히 건너뛴다 - 이 메서드는 항상 본 기능(채팅/복기 저장 등)이 이미 커밋된 "뒤"
        마지막 단계로 호출되므로, 여기서 잡지 못한 예외가 그대로 위로 전파되면 실제로는
        성공한 요청이 500으로 보여 클라이언트가 재시도하다 중복 리소스를 만들 위험이 있다.
        """
        try:
            await self._chunks.delete_for_source(source_type, source_id)

            if not content.strip():
                await self._session.commit()
                return

            model = self._settings.embedding_model
            try:
                embedding = await self._ollama.embed(text=content, model=model)
            except OllamaServiceError:
                logger.error(
                    "RAG 색인 실패 (임베딩 호출 에러): user_id=%s source_type=%s source_id=%s",
                    user_id,
                    source_type,
                    source_id,
                )
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
            else:
                logger.warning(
                    "RAG 색인 건너뜀 (빈 임베딩 반환): user_id=%s source_type=%s source_id=%s",
                    user_id,
                    source_type,
                    source_id,
                )
            await self._session.commit()
        except Exception:
            logger.exception(
                "RAG 색인 실패 (예상 못한 오류): user_id=%s source_type=%s source_id=%s",
                user_id,
                source_type,
                source_id,
            )
            await self._session.rollback()

    async def retrieve_relevant(self, user_id: uuid.UUID, query: str) -> list[str]:
        """query와 의미적으로 가까운 사용자 본인의 기존 기록 상위 K개를 반환한다.

        검색 실패는 전부 빈 리스트로 처리한다 - RAG는 답변 품질을 보강하는 부가 기능이라
        실패해도 채팅 자체는 평소대로 계속되어야 한다. index_content/forget_content(_bulk)와
        같은 이유로, 임베딩 호출 실패(OllamaServiceError)뿐 아니라 이 메서드 자신의
        DB 조회(list_for_user)에서 나는 예상 못한 오류(커넥션 드롭, 스테이트먼트 타임아웃
        등)도 삼켜야 한다 - 여기서 안 잡으면 학습챗/면접연습의 모든 턴마다 도는 이
        "부가 기능" 조회 하나가 그대로 채팅 자체를 500(REST)/비정상 종료(WS)로 만들어버려,
        이 클래스의 다른 세 메서드가 지키는 "RAG 실패는 절대 본 기능을 막지 않는다"는
        약속이 정작 가장 자주 불리는 이 메서드에서만 깨져 있었다.
        """
        model = self._settings.embedding_model
        try:
            candidates = await self._chunks.list_for_user(
                user_id, embedding_model=model, limit=self._settings.rag_max_candidate_chunks
            )
        except Exception:
            logger.exception("RAG 검색 실패 (예상 못한 DB 오류): user_id=%s", user_id)
            await self._session.rollback()
            return []
        if not candidates:
            return []

        try:
            query_embedding = await self._ollama.embed(text=query, model=model)
        except OllamaServiceError:
            logger.warning("RAG 검색 실패 (임베딩 호출 에러): user_id=%s", user_id)
            return []
        if not query_embedding:
            logger.warning("RAG 검색 건너뜀 (빈 임베딩 반환): user_id=%s", user_id)
            return []

        pairs = [(chunk.embedding, chunk.content) for chunk in candidates]
        try:
            return await asyncio.to_thread(_rank_top_k, query_embedding, pairs, self._settings.rag_top_k)
        except Exception:
            # list_for_user/embed 두 단계는 각자 예외를 이미 삼키는데, 이
            # 마지막 랭킹 단계만 아무 보호가 없었다 - 189라운드가 정리한
            # "이 메서드의 모든 단계가 예상 못한 오류를 삼켜야 한다"는
            # 원칙을 세 번째 단계에도 마저 적용한다.
            logger.exception("RAG 검색 실패 (예상 못한 랭킹 오류): user_id=%s", user_id)
            return []

    async def forget_content(self, source_type: str, source_id: uuid.UUID) -> None:
        """원본이 삭제될 때 색인도 함께 지운다.

        index_content와 같은 이유로 여기도 항상 원본(세션/복기 등)이 이미 커밋으로
        삭제된 "뒤" 호출되므로, 이 정리 단계에서 나는 예상 못한 DB 오류를 그대로
        전파하면 실제로는 성공한 삭제 요청이 500으로 보인다 - 조용히 삼키고 로그만
        남긴다."""
        try:
            await self._chunks.delete_for_source(source_type, source_id)
            await self._session.commit()
        except Exception:
            logger.exception(
                "RAG 색인 정리 실패 (예상 못한 오류): source_type=%s source_id=%s", source_type, source_id
            )
            await self._session.rollback()

    async def forget_content_bulk(self, source_type: str, source_ids: list[uuid.UUID]) -> None:
        """forget_content의 배치 버전 - 세션/연습 하나를 지울 때 그 안의 메시지/턴
        전부를 한 번의 DELETE+commit으로 처리한다(호출부마다 반복 호출하지 않도록).
        예외 처리 이유는 forget_content와 동일."""
        if not source_ids:
            return
        try:
            await self._chunks.delete_for_sources(source_type, source_ids)
            await self._session.commit()
        except Exception:
            logger.exception(
                "RAG 색인 일괄 정리 실패 (예상 못한 오류): source_type=%s source_id_count=%d",
                source_type,
                len(source_ids),
            )
            await self._session.rollback()
