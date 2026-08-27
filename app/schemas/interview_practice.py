import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings
from app.schemas.validators import NonBlankStr


class InterviewPracticeCreateRequest(BaseModel):
    topic: NonBlankStr = Field(..., min_length=1, max_length=255)
    model: str = Field(default="qwen2.5:3b", max_length=100)


class InterviewPracticeUpdateRequest(BaseModel):
    topic: NonBlankStr = Field(..., min_length=1, max_length=255)


class InterviewPracticeTurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_index: int
    question: str
    answer: str | None
    feedback: str | None
    created_at: datetime


class InterviewPracticeSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic: str
    model: str
    status: Literal["in_progress", "completed"]
    overall_feedback: str | None
    created_at: datetime
    updated_at: datetime


class InterviewPracticeSessionDetailResponse(InterviewPracticeSessionResponse):
    turns: list[InterviewPracticeTurnResponse]


class InterviewPracticeAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)

    @field_validator("answer")
    @classmethod
    def validate_answer_length(cls, value: str) -> str:
        # min_length=1은 빈 문자열("")만 막을 뿐 "   "처럼 공백만 있는 값은 그대로
        # 통과시킨다 - study.py의 validate_content_length(121라운드)와 같은 이유로,
        # 통과하면 빈 답변으로 AI 피드백을 생성하고 mark_answered_if_pending()의
        # 단발성 CAS(WHERE answer IS NULL)로 그 턴을 영구히 소비해버린다(재제출
        # 엔드포인트가 없음) - 121/122라운드가 "대응하는 WS 구현이 없어 범위 밖"
        # 이라는 이유로 미뤄뒀던 필드다.
        if not value.strip():
            raise ValueError("답변은 비어 있을 수 없습니다.")
        max_length = get_settings().max_prompt_length
        if len(value) > max_length:
            raise ValueError(f"답변은 최대 {max_length}자까지 허용됩니다.")
        return value


class InterviewPracticeAnswerResponse(BaseModel):
    answered_turn: InterviewPracticeTurnResponse
    next_turn: InterviewPracticeTurnResponse | None
