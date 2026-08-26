import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.clock import utcnow_naive
from app.core.config import get_settings
from app.schemas.validators import NonBlankStr


def _validate_interview_date_not_in_future(value: date) -> date:
    """면접 복기는 이미 치른 면접을 되짚는 기능이라, 아직 안 일어난(미래) 날짜는
    의미가 없다 - 정렬 기준으로도 쓰이는 값이라 터무니없는 값이 들어가면 UX가
    깨진다. "얼마나 먼 과거까지 허용할지"는 제품 판단이 필요해 하한은 두지
    않고(오래된 면접을 뒤늦게 기록하는 경우가 실제로 있을 수 있음), 명백히
    모순인 미래 날짜만 막는다."""
    today = utcnow_naive().date()
    if value > today:
        raise ValueError("interview_date는 미래 날짜일 수 없습니다.")
    return value


class InterviewReviewCreateRequest(BaseModel):
    company: NonBlankStr = Field(..., min_length=1, max_length=255)
    position: NonBlankStr = Field(..., min_length=1, max_length=255)
    interview_date: date
    content: str = Field(..., min_length=1)
    model: str = Field(default="qwen2.5:3b", max_length=100)

    @field_validator("interview_date")
    @classmethod
    def validate_interview_date(cls, value: date) -> date:
        return _validate_interview_date_not_in_future(value)

    @field_validator("content")
    @classmethod
    def validate_content_length(cls, value: str) -> str:
        max_length = get_settings().max_review_content_length
        if len(value) > max_length:
            raise ValueError(f"content는 최대 {max_length}자까지 허용됩니다.")
        return value


class InterviewReviewUpdateRequest(BaseModel):
    company: NonBlankStr | None = Field(default=None, min_length=1, max_length=255)
    position: NonBlankStr | None = Field(default=None, min_length=1, max_length=255)
    interview_date: date | None = None
    content: str | None = Field(default=None, min_length=1)

    @field_validator("interview_date")
    @classmethod
    def validate_interview_date(cls, value: date | None) -> date | None:
        if value is None:
            return value
        return _validate_interview_date_not_in_future(value)

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
