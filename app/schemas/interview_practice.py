import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings


class InterviewPracticeCreateRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=255)
    model: str = Field(default="qwen2.5:3b", max_length=100)


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
        max_length = get_settings().max_prompt_length
        if len(value) > max_length:
            raise ValueError(f"답변은 최대 {max_length}자까지 허용됩니다.")
        return value


class InterviewPracticeAnswerResponse(BaseModel):
    answered_turn: InterviewPracticeTurnResponse
    next_turn: InterviewPracticeTurnResponse | None
