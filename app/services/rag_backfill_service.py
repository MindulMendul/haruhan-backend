import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import get_settings
from app.db.models.interview_review import InterviewReview
from app.db.models.knowledge_chunk import KnowledgeChunk
from app.db.models.study_message import StudyMessage
from app.db.models.study_session import StudySession
from app.db.session import get_db
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)


async def backfill_unindexed_content(session: AsyncSession, rag_service: RagService) -> tuple[int, int]:
    """아직 색인이 없는(=임베딩 실패 등으로 knowledge_chunks에 없는) 학습챗 메시지 /
    면접 복기만 찾아서 색인한다. 이미 색인된 항목은 건드리지 않으므로, 전체를
    다시 긁는 `scripts/backfill_knowledge_chunks.py`와 달리 주기적으로 돌려도 비용이 작다.

    study_service/interview_review_service가 생성 시점에 이미 동기로 색인하므로,
    이 job이 매일 찾아내는 건 정상 상태에서는 임베딩 API 일시 실패 같은 예외적인
    경우뿐이다(전체 중 극소수) - 그런데 이전 구현은 "안 된 것만 찾는다"면서 정작
    학습챗 메시지/면접 복기 테이블 전체를 매번 파이썬으로 읽어와 이미 색인된
    knowledge_chunks 전체 id 집합과 대조했다. 서비스가 오래될수록 거의 모든 행이
    이미 색인된 상태가 되므로, 매일 도는 이 cron이 사실상 전체 이력 규모로 계속
    커지는 조회를 영원히 반복하는 셈이었다. LEFT JOIN ... WHERE 색인이 NULL로
    "아직 색인 안 된 행"만 DB 단에서 걸러내도록 바꿔서, 정상 상태에서는 해당
    쿼리가 반환하는 행 수(=재시도 대상)만큼만 비용이 들도록 했다.
    """
    message_chunk = aliased(KnowledgeChunk)
    message_rows = await session.execute(
        select(StudyMessage, StudySession.user_id)
        .join(StudySession, StudyMessage.session_id == StudySession.id)
        .outerjoin(
            message_chunk,
            (message_chunk.source_type == "study_message")
            & (message_chunk.source_id == StudyMessage.id),
        )
        .where(message_chunk.id.is_(None))
    )
    message_count = 0
    for message, user_id in message_rows.all():
        await rag_service.index_content(
            user_id=user_id,
            source_type="study_message",
            source_id=message.id,
            content=message.content,
        )
        message_count += 1

    review_chunk = aliased(KnowledgeChunk)
    review_rows = await session.execute(
        select(InterviewReview)
        .outerjoin(
            review_chunk,
            (review_chunk.source_type == "interview_review")
            & (review_chunk.source_id == InterviewReview.id),
        )
        .where(review_chunk.id.is_(None))
    )
    review_count = 0
    for review in review_rows.scalars().all():
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
    finally:
        # OllamaService는 요청/연결 범위 DI(get_ollama_service)를 안 거치는 이
        # 스케줄러 경로에서 직접 만들었으므로, 내부 httpx.AsyncClient도 직접
        # 닫아줘야 한다 - 안 그러면 하루에 한 번 도는 이 job이 매번 커넥션을
        # 새로 열고 정리 안 된 채로 버린다.
        await ollama_service.aclose()
