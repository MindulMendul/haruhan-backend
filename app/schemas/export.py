import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class StudyMessageExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class StudySessionExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    model: str
    created_at: datetime
    updated_at: datetime
    messages: list[StudyMessageExport]


class QuizQuestionExport(BaseModel):
    """정답/해설을 그대로 포함한다 - 본인 데이터 export이므로 퀴즈 풀이용 뷰와 달리
    가릴 이유가 없다."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_index: int
    question_text: str
    choices: list[str]
    correct_answer: str
    explanation: str


class QuizAnswerExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question_id: uuid.UUID
    selected_index: int
    is_correct: bool


class QuizAttemptExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    score: int
    total: int
    submitted_at: datetime
    answers: list[QuizAnswerExport]


class QuizExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source_study_session_id: uuid.UUID | None
    source_text: str | None
    created_at: datetime
    questions: list[QuizQuestionExport]
    attempts: list[QuizAttemptExport]


class InterviewPracticeTurnExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_index: int
    question: str
    answer: str | None
    feedback: str | None
    created_at: datetime


class InterviewPracticeSessionExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic: str
    model: str
    status: str
    overall_feedback: str | None
    created_at: datetime
    updated_at: datetime
    turns: list[InterviewPracticeTurnExport]


class InterviewReviewExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company: str
    position: str
    interview_date: date
    content: str
    model: str
    ai_feedback: str | None
    created_at: datetime
    updated_at: datetime


class UserDataExport(BaseModel):
    exported_at: datetime
    user_id: uuid.UUID
    study_sessions: list[StudySessionExport]
    quizzes: list[QuizExport]
    interview_practice_sessions: list[InterviewPracticeSessionExport]
    interview_reviews: list[InterviewReviewExport]
