import asyncio
from datetime import date

from app.core.config import get_settings
from app.repositories.interview_review_repository import InterviewReviewRepository
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.repositories.quiz_repository import QuizRepository
from app.repositories.study_message_repository import StudyMessageRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository
from app.services.rag_service import RagService
from scripts.backfill_knowledge_chunks import (
    _confirm_before_running,
    _redact_database_url,
    backfill_all_content,
)


class FakeEmbeddingOllamaService:
    async def embed(self, text: str, model: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def test_redact_database_url_hides_password():
    """확인 프롬프트에 대상 DB를 보여줄 때 비밀번호가 터미널 히스토리/로그에
    그대로 남지 않아야 한다 - 호스트/포트/DB이름만 남긴다."""
    redacted = _redact_database_url("postgresql+asyncpg://admin:supersecret@db.internal:5432/haruhan")
    assert redacted == "db.internal:5432/haruhan"
    assert "admin" not in redacted
    assert "supersecret" not in redacted


def test_confirm_before_running_proceeds_only_on_y():
    prompts_shown = []

    def _ask(prompt: str) -> str:
        prompts_shown.append(prompt)
        return "y"

    assert _confirm_before_running("postgresql://admin:supersecret@prod-db:5432/haruhan", ask=_ask) is True
    # 실제로 사용자에게 보여준 프롬프트 문자열 자체에도 비밀번호가 없어야 한다.
    assert "supersecret" not in prompts_shown[0]
    assert "prod-db:5432/haruhan" in prompts_shown[0]


def test_confirm_before_running_cancels_on_anything_else():
    """엔터만 치거나 y가 아닌 다른 입력을 하면 실수로 프로덕션 DB에 대고
    돌리는 걸 막아야 한다 - 기본값은 "아니오"다."""
    assert _confirm_before_running("postgresql://u:p@db:5432/x", ask=lambda _: "") is False
    assert _confirm_before_running("postgresql://u:p@db:5432/x", ask=lambda _: "n") is False
    assert _confirm_before_running("postgresql://u:p@db:5432/x", ask=lambda _: "yes") is False


def test_backfill_all_content_reindexes_everything_even_if_already_indexed(db_session_factory):
    """이 스크립트는 (매일 도는 rag_backfill_service.backfill_unindexed_content와
    달리) "아직 색인 안 된 것만"이 아니라 전체 이력을 대상으로 한다 - 이미
    색인된 항목도 다시 색인해야 한다(index_content가 같은 source의 기존 색인을
    먼저 지우고 새로 만들어서 몇 번을 다시 돌려도 안전한 것과 별개로, 이
    스크립트 자체의 목적이 "이미 색인된 것도 전부 다시 훑는" 일회성 전체
    재색인이다)."""
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            study_session = await StudySessionRepository(session).create(
                user_id=user.id, title="세션", model="qwen"
            )
            message = await StudyMessageRepository(session).create(
                session_id=study_session.id, role="user", content="이미 색인됨"
            )
            review = await InterviewReviewRepository(session).create(
                user_id=user.id,
                company="회사",
                position="포지션",
                interview_date=date(2026, 1, 1),
                content="복기 내용",
                model="qwen",
            )
            pasted_quiz = await QuizRepository(session).create(
                user_id=user.id, title="퀴즈", source_study_session_id=None, source_text="붙여넣은 소스"
            )
            derived_quiz = await QuizRepository(session).create(
                user_id=user.id, title="파생 퀴즈", source_study_session_id=study_session.id
            )
            await session.commit()

            rag = RagService(session=session, ollama_service=FakeEmbeddingOllamaService(), settings=settings)
            # message는 미리 색인해둔다 - 그래도 다시 색인 대상에 포함돼야 한다.
            await rag.index_content(
                user_id=user.id, source_type="study_message", source_id=message.id, content=message.content
            )

            message_count, review_count, quiz_count, turn_count = await backfill_all_content(session, rag)

            assert message_count == 1
            assert review_count == 1
            assert quiz_count == 1  # 직접 붙여넣은 퀴즈만 - 세션에서 파생된 퀴즈는 제외
            assert turn_count == 0

            chunks = KnowledgeChunkRepository(session)
            assert await chunks.get_indexed_source_ids("study_message") == {message.id}
            assert await chunks.get_indexed_source_ids("interview_review") == {review.id}
            assert await chunks.get_indexed_source_ids("quiz_source") == {pasted_quiz.id}
            assert derived_quiz.id not in await chunks.get_indexed_source_ids("quiz_source")

    asyncio.run(_run())
