import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeChunk(Base):
    """RAG 검색 대상이 되는 텍스트 조각 (사용자 본인의 기존 기록에서 나온 것만).

    source_id는 study_messages/interview_reviews 등 여러 테이블을 가리킬 수 있는
    다형적(polymorphic) 참조라 FK 제약을 걸지 않는다 - source_type으로만 구분한다.
    """

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        # KnowledgeChunkRepository.list_for_user(학습챗/면접연습 매 턴마다 RAG 검색 시
        # 호출됨)이 정확히 이 세 컬럼으로 필터/정렬한다. 이 테이블은 만료/정리 로직이
        # 없어 계정이 오래될수록 계속 쌓이기만 하므로, 단일 컬럼 인덱스(user_id)만으로는
        # embedding_model 필터링과 정렬을 인덱스 스캔 이후에 처리해야 해서 계정이 커질수록
        # 이 조회가 먼저 느려질 후보였다.
        Index(
            "ix_knowledge_chunks_user_id_embedding_model_created_at",
            "user_id",
            "embedding_model",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # pgvector 없이, 임베딩을 그대로 JSON 배열로 저장하고 검색 시 파이썬에서 코사인
    # 유사도를 계산한다. 개인/소규모 사용 스케일에서는 이걸로 충분하고, 별도 익스텐션/
    # 의존성이 필요 없다 (자료가 수천 청크 넘어가면 pgvector로 전환 고려).
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
