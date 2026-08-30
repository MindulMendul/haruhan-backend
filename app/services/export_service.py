import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow_naive
from app.db.models.user import User
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
from app.schemas.user import UserResponse


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

    async def export_user_data(self, user: User) -> UserDataExport:
        user_id = user.id
        return UserDataExport(
            exported_at=utcnow_naive(),
            user_id=user_id,
            user=UserResponse.model_validate(user),
            study_sessions=await self._build_study_sessions(user_id),
            quizzes=await self._build_quizzes(user_id),
            interview_practice_sessions=await self._build_practice_sessions(user_id),
            interview_reviews=[
                InterviewReviewExport.model_validate(review)
                for review in await self._reviews.list_all_for_user(user_id)
            ],
        )

    async def _build_study_sessions(self, user_id: uuid.UUID) -> list[StudySessionExport]:
        """세션마다 메시지를 따로 조회하면 세션 개수만큼 쿼리가 느는 N+1이 된다 -
        이 export는 계정이 오래될수록 세션 수가 계속 늘어나는 대상이라, 세션에
        속한 전체 메시지를 한 번에 가져와 파이썬에서 session_id별로 묶는다."""
        study_sessions = await self._study_sessions.list_all_for_user(user_id)
        messages = await self._study_messages.list_for_sessions([s.id for s in study_sessions])
        messages_by_session: dict[uuid.UUID, list] = {}
        for message in messages:
            messages_by_session.setdefault(message.session_id, []).append(message)

        return [
            StudySessionExport(
                id=study_session.id,
                title=study_session.title,
                model=study_session.model,
                created_at=study_session.created_at,
                updated_at=study_session.updated_at,
                messages=[
                    StudyMessageExport.model_validate(m)
                    for m in messages_by_session.get(study_session.id, [])
                ],
            )
            for study_session in study_sessions
        ]

    async def _build_quizzes(self, user_id: uuid.UUID) -> list[QuizExport]:
        """이전에는 퀴즈마다 문항 조회를, 시도마다 답안 조회를 따로 날려서 퀴즈/
        시도 개수만큼 쿼리가 느는 N+1이었다 - 전부 한 번씩만 조회해 파이썬에서
        quiz_id/attempt_id별로 묶는다."""
        quizzes = await self._quizzes.list_all_for_user(user_id)
        quiz_ids = [q.id for q in quizzes]

        questions_by_quiz: dict[uuid.UUID, list] = {}
        for question in await self._questions.list_for_quizzes(quiz_ids):
            questions_by_quiz.setdefault(question.quiz_id, []).append(question)

        attempts_by_quiz: dict[uuid.UUID, list] = {}
        for attempt in await self._attempts.list_for_user(user_id):
            attempts_by_quiz.setdefault(attempt.quiz_id, []).append(attempt)

        attempt_ids = [a.id for attempts in attempts_by_quiz.values() for a in attempts]
        answers_by_attempt: dict[uuid.UUID, list] = {}
        for answer in await self._answers.list_for_attempts(attempt_ids):
            answers_by_attempt.setdefault(answer.attempt_id, []).append(answer)

        exports = []
        for quiz in quizzes:
            attempt_exports = [
                QuizAttemptExport(
                    id=attempt.id,
                    score=attempt.score,
                    total=attempt.total,
                    submitted_at=attempt.submitted_at,
                    answers=[
                        QuizAnswerExport.model_validate(a)
                        for a in answers_by_attempt.get(attempt.id, [])
                    ],
                )
                for attempt in attempts_by_quiz.get(quiz.id, [])
            ]
            exports.append(
                QuizExport(
                    id=quiz.id,
                    title=quiz.title,
                    source_study_session_id=quiz.source_study_session_id,
                    source_text=quiz.source_text,
                    created_at=quiz.created_at,
                    questions=[
                        QuizQuestionExport.model_validate(q) for q in questions_by_quiz.get(quiz.id, [])
                    ],
                    attempts=attempt_exports,
                )
            )
        return exports

    async def _build_practice_sessions(self, user_id: uuid.UUID) -> list[InterviewPracticeSessionExport]:
        """세션마다 턴을 따로 조회하면 세션 개수만큼 쿼리가 느는 N+1이 된다 -
        전체 턴을 한 번에 가져와 파이썬에서 session_id별로 묶는다."""
        practice_sessions = await self._practice_sessions.list_all_for_user(user_id)
        turns = await self._practice_turns.list_for_sessions([s.id for s in practice_sessions])
        turns_by_session: dict[uuid.UUID, list] = {}
        for turn in turns:
            turns_by_session.setdefault(turn.session_id, []).append(turn)

        return [
            InterviewPracticeSessionExport(
                id=practice_session.id,
                topic=practice_session.topic,
                model=practice_session.model,
                status=practice_session.status,
                overall_feedback=practice_session.overall_feedback,
                created_at=practice_session.created_at,
                updated_at=practice_session.updated_at,
                turns=[
                    InterviewPracticeTurnExport.model_validate(t)
                    for t in turns_by_session.get(practice_session.id, [])
                ],
            )
            for practice_session in practice_sessions
        ]
