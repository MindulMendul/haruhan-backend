import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import get_settings


class QuizCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    study_session_id: uuid.UUID | None = None
    source_text: str | None = Field(default=None, min_length=1)
    question_count: int | None = Field(default=None, ge=1)
    model: str = Field(default="qwen2.5:3b", max_length=100)

    @model_validator(mode="after")
    def _validate_source_and_count(self) -> "QuizCreateRequest":
        settings = get_settings()

        if not self.study_session_id and not self.source_text:
            raise ValueError("study_session_id 또는 source_text 중 하나는 필요합니다.")
        if self.study_session_id and self.source_text:
            raise ValueError("study_session_id와 source_text는 동시에 지정할 수 없습니다.")
        if self.source_text and len(self.source_text) > settings.max_quiz_source_length:
            raise ValueError(f"source_text는 최대 {settings.max_quiz_source_length}자까지 허용됩니다.")

        if self.question_count is None:
            self.question_count = settings.default_quiz_question_count
        elif self.question_count > settings.max_quiz_question_count:
            raise ValueError(f"question_count는 최대 {settings.max_quiz_question_count}까지 허용됩니다.")

        return self


class QuizResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source_study_session_id: uuid.UUID | None
    created_at: datetime


class QuizQuestionPublic(BaseModel):
    """정답/해설을 노출하지 않는 문제 목록용 응답."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_index: int
    question_text: str
    choices: list[str]


class QuizDetailResponse(QuizResponse):
    questions: list[QuizQuestionPublic]


class QuizSubmitAnswerItem(BaseModel):
    question_id: uuid.UUID
    selected_index: int = Field(..., ge=0)


class QuizSubmitRequest(BaseModel):
    answers: list[QuizSubmitAnswerItem] = Field(..., min_length=1)


class QuizAnswerResult(BaseModel):
    question_id: uuid.UUID
    selected_index: int
    is_correct: bool
    correct_answer: str
    explanation: str


class QuizResultResponse(BaseModel):
    attempt_id: uuid.UUID
    score: int
    total: int
    submitted_at: datetime
    answers: list[QuizAnswerResult]
