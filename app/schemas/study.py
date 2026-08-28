import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import get_settings
from app.schemas.validators import NonBlankStr, UtcDatetime


class StudySessionCreateRequest(BaseModel):
    title: NonBlankStr = Field(..., min_length=1, max_length=255)
    model: str = Field(default="qwen2.5:3b", max_length=100)


class StudySessionUpdateRequest(BaseModel):
    title: NonBlankStr = Field(..., min_length=1, max_length=255)


class StudySessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    model: str
    created_at: UtcDatetime
    updated_at: UtcDatetime


class StudyMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: UtcDatetime


class StudySessionDetailResponse(StudySessionResponse):
    messages: list[StudyMessageResponse] = Field(default_factory=list)


class StudyMessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, value: str) -> str:
        # WS 스트리밍 경로(routes/study.py의 stream_message)는 공백만 있는
        # content를 "content는 비어 있을 수 없습니다"로 거부하고 LLM을 호출하지
        # 않는다. REST 경로는 min_length=1만으로는 " " 같은 공백 문자열을
        # 그대로 통과시켜 빈 메시지가 저장되고 불필요한 LLM 호출까지 발생했다 -
        # 두 경로가 동일한 기능(send_message)에 대해 다르게 동작하지 않도록
        # REST도 WS와 같은 규칙으로 맞춘다.
        if not value.strip():
            raise ValueError("content는 비어 있을 수 없습니다.")
        max_length = get_settings().max_prompt_length
        if len(value) > max_length:
            raise ValueError(f"메시지는 최대 {max_length}자까지 허용됩니다.")
        return value


class StudyMessageCreateResponse(BaseModel):
    user_message: StudyMessageResponse
    assistant_message: StudyMessageResponse
