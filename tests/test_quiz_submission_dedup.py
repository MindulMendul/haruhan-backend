import asyncio
from datetime import timedelta

from app.core.clock import utcnow_naive
from app.repositories.quiz_repository import QuizQuestionRepository, QuizRepository
from app.repositories.user_repository import UserRepository
from app.services.quiz_service import QuizService


class UnusedOllamaService:
    """이 테스트는 채점만 다루므로 Ollama 호출이 실제로 일어나면 안 된다."""

    async def generate_json(self, prompt, model, schema):
        raise AssertionError("퀴즈 재제출 테스트에서는 Ollama가 호출되면 안 됨")


class UnusedRagService:
    """RAG 색인은 퀴즈 생성 시에만 일어나므로, 제출(채점) 테스트에서는 호출되면 안 된다."""

    async def index_content(self, user_id, source_type, source_id, content):
        raise AssertionError("퀴즈 재제출 테스트에서는 RAG 색인이 호출되면 안 됨")


def test_resubmitting_identical_answers_after_window_creates_new_attempt(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            quiz = await QuizRepository(session).create(
                user_id=user.id, title="퀴즈", source_study_session_id=None
            )
            question = await QuizQuestionRepository(session).create(
                quiz_id=quiz.id,
                order_index=0,
                question_text="질문",
                choices=["A", "B"],
                correct_answer="A",
                explanation="설명",
            )
            await session.commit()

            service = QuizService(
                session=session, ollama_service=UnusedOllamaService(), rag_service=UnusedRagService()
            )

            first_attempt, _ = await service.submit_answers(
                quiz_id=quiz.id, user_id=user.id, answers=[(question.id, 0)]
            )

            # 직전 제출을 중복 감지 윈도우(5초) 밖으로 밀어내서, 시간이 실제로 많이
            # 지난 뒤 똑같은 답을 다시 제출한 상황(=진짜 재도전)을 흉내낸다.
            first_attempt.submitted_at = utcnow_naive() - timedelta(minutes=1)
            await session.commit()

            second_attempt, _ = await service.submit_answers(
                quiz_id=quiz.id, user_id=user.id, answers=[(question.id, 0)]
            )

            assert second_attempt.id != first_attempt.id

    asyncio.run(_run())


def test_resubmitting_identical_answers_within_window_reuses_attempt(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            quiz = await QuizRepository(session).create(
                user_id=user.id, title="퀴즈", source_study_session_id=None
            )
            question = await QuizQuestionRepository(session).create(
                quiz_id=quiz.id,
                order_index=0,
                question_text="질문",
                choices=["A", "B"],
                correct_answer="A",
                explanation="설명",
            )
            await session.commit()

            service = QuizService(
                session=session, ollama_service=UnusedOllamaService(), rag_service=UnusedRagService()
            )

            first_attempt, first_graded = await service.submit_answers(
                quiz_id=quiz.id, user_id=user.id, answers=[(question.id, 0)]
            )
            second_attempt, second_graded = await service.submit_answers(
                quiz_id=quiz.id, user_id=user.id, answers=[(question.id, 0)]
            )

            assert second_attempt.id == first_attempt.id
            assert [(q.id, idx, correct) for q, idx, correct in second_graded] == [
                (q.id, idx, correct) for q, idx, correct in first_graded
            ]

    asyncio.run(_run())
