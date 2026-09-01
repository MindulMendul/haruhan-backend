import asyncio
from datetime import date, timedelta

from app.core.clock import utcnow_naive
from app.repositories.interview_practice_repository import (
    InterviewPracticeSessionRepository,
    InterviewPracticeTurnRepository,
)
from app.repositories.interview_review_repository import InterviewReviewRepository
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.repositories.quiz_attempt_repository import QuizAnswerRepository, QuizAttemptRepository
from app.repositories.quiz_repository import QuizQuestionRepository, QuizRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository


def test_deleting_user_cascades_to_all_owned_data(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()

            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen2.5:3b"
            )
            message = await StudyMessageRepository(session).create(
                session_id=study_session.id, role="user", content="내용"
            )

            quiz = await QuizRepository(session).create(
                user_id=user.id, title="퀴즈", source_study_session_id=study_session.id
            )
            question = await QuizQuestionRepository(session).create(
                quiz_id=quiz.id,
                order_index=0,
                question_text="질문",
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
            await InterviewPracticeTurnRepository(session).create(
                session_id=practice_session.id, order_index=0, question="질문"
            )

            review = await InterviewReviewRepository(session).create(
                user_id=user.id,
                company="회사",
                position="포지션",
                interview_date=date(2026, 1, 1),
                content="복기 내용",
                model="qwen2.5:3b",
            )

            chunks = KnowledgeChunkRepository(session)
            await chunks.create(
                user_id=user.id,
                source_type="study_message",
                source_id=message.id,
                content="내용",
                embedding=[1.0, 0.0, 0.0],
                embedding_model="nomic-embed-text",
            )

            refresh_tokens = RefreshTokenRepository(session)
            await refresh_tokens.create(
                user_id=user.id, token_hash="a-hash", expires_at=utcnow_naive() + timedelta(days=1)
            )

            await session.commit()

            await UserRepository(session).delete(user)
            await session.commit()

            assert await UserRepository(session).get_by_id(user.id) is None
            assert (
                await StudySessionRepository(session).get_for_user(study_session.id, user.id) is None
            )
            assert await StudyMessageRepository(session).list_for_session(study_session.id) == []
            assert await QuizRepository(session).get_for_user(quiz.id, user.id) is None
            assert await QuizQuestionRepository(session).list_for_quiz(quiz.id) == []
            assert await QuizAnswerRepository(session).list_for_attempt(attempt.id) == []
            assert (
                await InterviewPracticeSessionRepository(session).get_for_user(
                    practice_session.id, user.id
                )
                is None
            )
            assert (
                await InterviewPracticeTurnRepository(session).list_for_session(practice_session.id)
                == []
            )
            assert await InterviewReviewRepository(session).get_for_user(review.id, user.id) is None
            assert await chunks.get_indexed_source_ids("study_message") == set()
            assert await refresh_tokens.get_by_hash("a-hash") is None

    asyncio.run(_run())
