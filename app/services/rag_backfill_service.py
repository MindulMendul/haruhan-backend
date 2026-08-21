import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.interview_review import InterviewReview
from app.db.models.study_message import StudyMessage
from app.db.models.study_session import StudySession
from app.db.session import get_db
from app.repositories.knowledge_chunk_repository import KnowledgeChunkRepository
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)


async def backfill_unindexed_content(session: AsyncSession, rag_service: RagService) -> tuple[int, int]:
    """아직 색인이 없는(=임베딩 실패 등으로 knowledge_chunks에 없는) 학습챗 메시지 /
    면접 복기만 찾아서 색인한다. 이미 색인된 항목은 건드리지 않으므로, 전체를
    다시 긁는 `scripts/backfill_knowledge_chunks.py`와 달리 주기적으로 돌려도 비용이 작다.
    """
    chunks = KnowledgeChunkRepository(session)

    message_rows = await session.execute(
        select(StudyMessage, StudySession.user_id).join(
            StudySession, StudyMessage.session_id == StudySession.id
        )
    )
    indexed_message_ids = await chunks.get_indexed_source_ids("study_message")
    message_count = 0
    for message, user_id in message_rows.all():
        if message.id in indexed_message_ids:
            continue
        await rag_service.index_content(
            user_id=user_id,
            source_type="study_message",
            source_id=message.id,
            content=message.content,
        )
        message_count += 1

    review_rows = await session.execute(select(InterviewReview))
    indexed_review_ids = await chunks.get_indexed_source_ids("interview_review")
    review_count = 0
    for review in review_rows.scalars().all():
        if review.id in indexed_review_ids:
            continue
        await rag_service.index_content(
            user_id=review.user_id,
            source_type="interview_review",
            source_id=review.id,
            content=review.content,
        )
        review_count += 1

    return message_count, review_count


async def run_scheduled_rag_backfill() -> None:
    """스케줄러 job 엔트리포인트: 아직 색인 안 된 항목만 재시도한다."""
    settings = get_settings()
    ollama_service = OllamaService(base_url=settings.ollama_base_url)
    try:
        async for session in get_db():
            rag_service = RagService(session=session, ollama_service=ollama_service, settings=settings)
            message_count, review_count = await backfill_unindexed_content(session, rag_service)
        logger.info(
            "[RAG 백필] 새로 색인: study_message %d건, interview_review %d건",
            message_count,
            review_count,
        )
    except RuntimeError:
        logger.warning("[RAG 백필] DB 엔진이 초기화되지 않아 건너뜁니다.")
    except Exception:
        logger.exception("[RAG 백필] 실패")
