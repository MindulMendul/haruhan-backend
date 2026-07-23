import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings


class StudySessionCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    model: str = Field(default="qwen2.5:3b", max_length=100)


class StudySessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    model: str
    created_at: datetime
    updated_at: datetime


class StudyMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class StudySessionDetailResponse(StudySessionResponse):
    messages: list[StudyMessageResponse] = Field(default_factory=list)


class StudyMessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, value: str) -> str:
        max_length = get_settings().max_prompt_length
        if len(value) > max_length:
            raise ValueError(f"메시지는 최대 {max_length}자까지 허용됩니다.")
        return value


class StudyMessageCreateResponse(BaseModel):
    user_message: StudyMessageResponse
    assistant_message: StudyMessageResponse
