import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserResponse
from app.schemas.validators import UtcDatetime


class StudyMessageExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    created_at: UtcDatetime


class StudySessionExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    model: str
    created_at: UtcDatetime
    updated_at: UtcDatetime
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
    submitted_at: UtcDatetime
    answers: list[QuizAnswerExport]


class QuizExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source_study_session_id: uuid.UUID | None
    source_text: str | None
    created_at: UtcDatetime
    questions: list[QuizQuestionExport]
    attempts: list[QuizAttemptExport]


class InterviewPracticeTurnExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_index: int
    question: str
    answer: str | None
    feedback: str | None
    created_at: UtcDatetime


class InterviewPracticeSessionExport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic: str
    model: str
    status: str
    overall_feedback: str | None
    created_at: UtcDatetime
    updated_at: UtcDatetime
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
    created_at: UtcDatetime
    updated_at: UtcDatetime


class UserDataExport(BaseModel):
    exported_at: UtcDatetime
    # user_id는 하위 호환을 위해 남겨둔다 - user.id와 항상 같은 값이다.
    user_id: uuid.UUID
    # "내 데이터 전체 내보내기"인데 정작 계정 자체(가입 이메일/가입일/게스트 여부)는
    # 빠져 있었다 - GET /users/me가 이미 노출하는 것과 같은 정보를 여기서도
    # 재사용한다(UserResponse).
    user: UserResponse
    study_sessions: list[StudySessionExport]
    quizzes: list[QuizExport]
    interview_practice_sessions: list[InterviewPracticeSessionExport]
    interview_reviews: list[InterviewReviewExport]
