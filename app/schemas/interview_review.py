import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings


class InterviewReviewCreateRequest(BaseModel):
    company: str = Field(..., min_length=1, max_length=255)
    position: str = Field(..., min_length=1, max_length=255)
    interview_date: date
    content: str = Field(..., min_length=1)
    model: str = Field(default="qwen2.5:3b", max_length=100)

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, value: str) -> str:
        max_length = get_settings().max_review_content_length
        if len(value) > max_length:
            raise ValueError(f"content는 최대 {max_length}자까지 허용됩니다.")
        return value


class InterviewReviewUpdateRequest(BaseModel):
    company: str | None = Field(default=None, min_length=1, max_length=255)
    position: str | None = Field(default=None, min_length=1, max_length=255)
    interview_date: date | None = None
    content: str | None = Field(default=None, min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, value: str | None) -> str | None:
        if value is None:
            return value
        max_length = get_settings().max_review_content_length
        if len(value) > max_length:
            raise ValueError(f"content는 최대 {max_length}자까지 허용됩니다.")
        return value


class InterviewReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company: str
    position: str
    interview_date: date
    content: str
    ai_feedback: str | None
    created_at: datetime
    updated_at: datetime
