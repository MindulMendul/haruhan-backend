import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 학습 세션에서 생성됐다면 출처를 남긴다. 세션이 삭제돼도 퀴즈 자체는 남긴다 (SET NULL).
    source_study_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("study_sessions.id", ondelete="SET NULL"), nullable=True
    )
    # source_study_session_id가 없는(=사용자가 직접 붙여넣은) 경우에만 채워진다.
    # 이 텍스트는 study_message/interview_review와 달리 다른 어떤 테이블에도
    # 저장되지 않아서, 여기 남겨두지 않으면 퀴즈 생성 시점의 RAG 색인(임베딩
    # 호출)이 일시적으로 실패했을 때 원본을 영영 복구할 방법이 없다 - 그
    # 실패를 rag_backfill_service가 나중에 재시도하려면 재시도할 원본이
    # 있어야 한다.
    source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
