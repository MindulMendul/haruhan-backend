import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow_naive
from app.db.base import Base


class StudyMessage(Base):
    __tablename__ = "study_messages"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="ck_study_messages_role"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("study_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # DB의 server_default=now() 대신 파이썬 쪽에서 마이크로초 정밀도로 직접 찍는다 -
    # SQLite의 CURRENT_TIMESTAMP는 초 단위라, 같은 요청 안에서 몇 ms 사이에 만들어지는
    # user/assistant 메시지 쌍의 순서를 created_at만으로 구분 못 하는 문제가 있다
    # (QuizAttempt.submitted_at과 같은 이유).
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
