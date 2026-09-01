import asyncio
from datetime import date

from app.repositories.interview_practice_repository import (
    InterviewPracticeSessionRepository,
    InterviewPracticeTurnRepository,
)
from app.repositories.interview_review_repository import InterviewReviewRepository
from app.repositories.quiz_attempt_repository import QuizAnswerRepository, QuizAttemptRepository
from app.repositories.quiz_repository import QuizQuestionRepository, QuizRepository
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository
from app.services.export_service import ExportService


def test_export_user_data_includes_all_record_types(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()

            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            await StudyMessageRepository(session).create(
                session_id=study_session.id, role="user", content="질문"
            )
            await StudyMessageRepository(session).create(
                session_id=study_session.id, role="assistant", content="답변"
            )

            quiz = await QuizRepository(session).create(
                user_id=user.id, title="퀴즈", source_study_session_id=study_session.id
            )
            question = await QuizQuestionRepository(session).create(
                quiz_id=quiz.id,
                order_index=0,
                question_text="질문?",
                choices=["A", "B"],
                correct_answer="A",
                explanation="설명",
            )
            attempt = await QuizAttemptRepository(session).create(
                quiz_id=quiz.id, user_id=user.id, score=1, total=1
            )
            await QuizAnswerRepository(session).create(
                attempt_id=attempt.id, question_id=question.id, selected_index=0, is_correct=True
            )

            practice_session = await InterviewPracticeSessionRepository(session).create(
                user_id=user.id, topic="주제", model="qwen2.5:3b"
            )
            turn = await InterviewPracticeTurnRepository(session).create(
                session_id=practice_session.id, order_index=0, question="면접 질문"
            )
            turn.answer = "면접 답변"
            turn.feedback = "피드백"

            await InterviewReviewRepository(session).create(
                user_id=user.id,
                company="회사",
                position="포지션",
                interview_date=date(2026, 1, 1),
                content="복기 내용",
                model="qwen2.5:3b",
            )
            await session.commit()

            export = await ExportService(session).export_user_data(user)

            assert export.user_id == user.id
            assert export.user.id == user.id
            assert export.user.email is None
            assert export.user.is_guest is True
            assert export.user.created_at == user.created_at
            assert len(export.study_sessions) == 1
            assert [m.content for m in export.study_sessions[0].messages] == ["질문", "답변"]

            assert len(export.quizzes) == 1
            assert export.quizzes[0].questions[0].correct_answer == "A"
            assert len(export.quizzes[0].attempts) == 1
            assert export.quizzes[0].attempts[0].answers[0].is_correct is True

            assert len(export.interview_practice_sessions) == 1
            assert export.interview_practice_sessions[0].turns[0].answer == "면접 답변"

            assert len(export.interview_reviews) == 1
            assert export.interview_reviews[0].company == "회사"

    asyncio.run(_run())


def test_export_user_data_returns_empty_lists_for_new_user(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            export = await ExportService(session).export_user_data(user)

            assert export.study_sessions == []
            assert export.quizzes == []
            assert export.interview_practice_sessions == []
            assert export.interview_reviews == []

    asyncio.run(_run())


def test_export_user_data_includes_email_and_is_guest_false_for_real_account(db_session_factory):
    """"내 데이터 전체 내보내기"인데 정작 계정 자체(가입 이메일/가입일/게스트 여부)는
    export_user_data가 user_id만 넘겨받아 빠져 있었다 - GET /users/me가 이미
    노출하는 UserResponse를 그대로 재사용해 채운다. 실계정에서 email이 채워지고
    is_guest가 False인지 확인한다(게스트 케이스는 위 다른 테스트가 확인함)."""

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create(
                email="export-user@example.com", hashed_password="hashed"
            )
            await session.commit()

            export = await ExportService(session).export_user_data(user)

            assert export.user.email == "export-user@example.com"
            assert export.user.is_guest is False

    asyncio.run(_run())


def test_export_user_data_only_includes_own_records(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            other_user = await UserRepository(session).create_guest()
            await StudySessionRepository(session).create(
                user_id=other_user.id, title="다른 사람 세션", model="qwen2.5:3b"
            )
            await session.commit()

            export = await ExportService(session).export_user_data(user)
            assert export.study_sessions == []

    asyncio.run(_run())
