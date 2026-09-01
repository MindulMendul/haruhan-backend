import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow_naive
from app.db.base import Base


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False)
    # DB의 server_default=now() 대신 파이썬 쪽에서 마이크로초 정밀도로 직접 찍는다 -
    # SQLite의 CURRENT_TIMESTAMP는 초 단위라, 같은 퀴즈를 짧은 간격으로 다시 제출하면
    # "가장 최근 제출"을 submitted_at만으로 구분 못 하는 문제가 있었다(오답노트 재도전
    # 시나리오에서 실제로 재현됨).
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive, nullable=False)
