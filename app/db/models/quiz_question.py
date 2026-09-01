import uuid

from sqlalchemy import JSON, ForeignKey, Integer, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    choices: Mapped[list] = mapped_column(JSON, nullable=False)
    # AI가 생성한 correct_answer는 choices 중 하나와 문자 그대로 일치해야 하는데,
    # choices(JSON)/question_text/explanation은 전부 길이 제한이 없는 반면 이
    # 컬럼만 String(500)이었다 - LLM 출력 변동으로 500자를 넘는 보기가 나오면
    # (서비스 계층은 choices 소속 여부만 검증하고 길이는 안 봄) INSERT가
    # DataError(StringDataRightTruncation)로 실패해 처리되지 않은 500이 됐다.
    # choices와 동일한 무제한 텍스트로 맞춘다.
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
