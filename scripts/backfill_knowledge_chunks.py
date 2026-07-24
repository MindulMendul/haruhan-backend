"""기존 학습챗 메시지 / 면접 복기를 RAG 색인 대상(knowledge_chunks)으로 백필한다.

RagService.index_content()는 같은 source에 대한 기존 색인을 먼저 지우고 새로 만들기 때문에
이 스크립트는 몇 번을 다시 돌려도 안전하다 (idempotent).

사용법 (저장소 루트에서):
    DATABASE_URL=... OLLAMA_BASE_URL=... JWT_SECRET_KEY=... python -m scripts.backfill_knowledge_chunks
"""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models.interview_review import InterviewReview
from app.db.models.study_message import StudyMessage
from app.db.models.study_session import StudySession
from app.db.session import to_asyncpg_url
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다.")

    engine = create_async_engine(to_asyncpg_url(settings.database_url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    ollama_service = OllamaService(base_url=settings.ollama_base_url)

    try:
        async with session_factory() as session:
            rag_service = RagService(session=session, ollama_service=ollama_service, settings=settings)

            message_rows = await session.execute(
                select(StudyMessage, StudySession.user_id).join(
                    StudySession, StudyMessage.session_id == StudySession.id
                )
            )
            messages = message_rows.all()
            for index, (message, user_id) in enumerate(messages, start=1):
                await rag_service.index_content(
                    user_id=user_id,
                    source_type="study_message",
                    source_id=message.id,
                    content=message.content,
                )
                logger.info("[study_message %d/%d] 색인 완료: %s", index, len(messages), message.id)

            review_rows = await session.execute(select(InterviewReview))
            reviews = list(review_rows.scalars().all())
            for index, review in enumerate(reviews, start=1):
                await rag_service.index_content(
                    user_id=review.user_id,
                    source_type="interview_review",
                    source_id=review.id,
                    content=review.content,
                )
                logger.info("[interview_review %d/%d] 색인 완료: %s", index, len(reviews), review.id)

        logger.info("백필 완료: study_message %d건, interview_review %d건", len(messages), len(reviews))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(backfill())
