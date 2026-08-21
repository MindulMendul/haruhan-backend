import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.repositories.interview_practice_repository import (
    InterviewPracticeSessionRepository,
    InterviewPracticeTurnRepository,
)
from app.repositories.interview_review_repository import InterviewReviewRepository
from app.repositories.quiz_attempt_repository import QuizAnswerRepository, QuizAttemptRepository
from app.repositories.quiz_repository import QuizQuestionRepository, QuizRepository
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.schemas.export import (
    InterviewPracticeSessionExport,
    InterviewPracticeTurnExport,
    InterviewReviewExport,
    QuizAnswerExport,
    QuizAttemptExport,
    QuizExport,
    QuizQuestionExport,
    StudyMessageExport,
    StudySessionExport,
    UserDataExport,
)


class ExportService:
    """사용자 본인의 학습챗/퀴즈/면접연습/면접복기 기록을 JSON으로 내보낸다."""

    def __init__(self, session: AsyncSession) -> None:
        self._study_sessions = StudySessionRepository(session)
        self._study_messages = StudyMessageRepository(session)
        self._quizzes = QuizRepository(session)
        self._questions = QuizQuestionRepository(session)
        self._attempts = QuizAttemptRepository(session)
        self._answers = QuizAnswerRepository(session)
        self._practice_sessions = InterviewPracticeSessionRepository(session)
        self._practice_turns = InterviewPracticeTurnRepository(session)
        self._reviews = InterviewReviewRepository(session)

    async def export_user_data(self, user_id: uuid.UUID) -> UserDataExport:
        return UserDataExport(
            exported_at=utcnow_naive(),
            user_id=user_id,
            study_sessions=await self._build_study_sessions(user_id),
            quizzes=await self._build_quizzes(user_id),
            interview_practice_sessions=await self._build_practice_sessions(user_id),
            interview_reviews=[
                InterviewReviewExport.model_validate(review)
                for review in await self._reviews.list_all_for_user(user_id)
            ],
        )

    async def _build_study_sessions(self, user_id: uuid.UUID) -> list[StudySessionExport]:
        exports = []
        for study_session in await self._study_sessions.list_all_for_user(user_id):
            messages = await self._study_messages.list_for_session(study_session.id)
            exports.append(
                StudySessionExport(
                    id=study_session.id,
                    title=study_session.title,
                    model=study_session.model,
                    created_at=study_session.created_at,
                    updated_at=study_session.updated_at,
                    messages=[StudyMessageExport.model_validate(m) for m in messages],
                )
            )
        return exports

    async def _build_quizzes(self, user_id: uuid.UUID) -> list[QuizExport]:
        attempts_by_quiz: dict[uuid.UUID, list] = {}
        for attempt in await self._attempts.list_for_user(user_id):
            attempts_by_quiz.setdefault(attempt.quiz_id, []).append(attempt)

        exports = []
        for quiz in await self._quizzes.list_all_for_user(user_id):
            questions = await self._questions.list_for_quiz(quiz.id)
            attempt_exports = []
            for attempt in attempts_by_quiz.get(quiz.id, []):
                answers = await self._answers.list_for_attempt(attempt.id)
                attempt_exports.append(
                    QuizAttemptExport(
                        id=attempt.id,
                        score=attempt.score,
                        total=attempt.total,
                        submitted_at=attempt.submitted_at,
                        answers=[QuizAnswerExport.model_validate(a) for a in answers],
                    )
                )
            exports.append(
                QuizExport(
                    id=quiz.id,
                    title=quiz.title,
                    source_study_session_id=quiz.source_study_session_id,
                    created_at=quiz.created_at,
                    questions=[QuizQuestionExport.model_validate(q) for q in questions],
                    attempts=attempt_exports,
                )
            )
        return exports

    async def _build_practice_sessions(self, user_id: uuid.UUID) -> list[InterviewPracticeSessionExport]:
        exports = []
        for practice_session in await self._practice_sessions.list_all_for_user(user_id):
            turns = await self._practice_turns.list_for_session(practice_session.id)
            exports.append(
                InterviewPracticeSessionExport(
                    id=practice_session.id,
                    topic=practice_session.topic,
                    model=practice_session.model,
                    status=practice_session.status,
                    overall_feedback=practice_session.overall_feedback,
                    created_at=practice_session.created_at,
                    updated_at=practice_session.updated_at,
                    turns=[InterviewPracticeTurnExport.model_validate(t) for t in turns],
                )
            )
        return exports
