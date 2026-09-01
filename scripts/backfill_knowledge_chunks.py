"""기존 학습챗 메시지 / 면접 복기 / 직접 붙여넣은 퀴즈 소스 / 면접연습 문답을
RAG 색인 대상(knowledge_chunks)으로 백필한다.

RagService.index_content()는 같은 source에 대한 기존 색인을 먼저 지우고 새로 만들기 때문에
이 스크립트는 몇 번을 다시 돌려도 안전하다 (idempotent). 다만 전체 이력을 훑으며 Ollama
임베딩 API를 순차로 호출하므로(계정이 클수록 오래 걸림), 실수로 프로덕션 DATABASE_URL을
가리킨 채로 로컬에서 돌리는 사고를 막기 위해 실행 전 대상 DB를 보여주고 확인을 받는다
(비대화형 환경에서는 --yes로 건너뛸 수 있다).

사용법 (저장소 루트에서):
    DATABASE_URL=... OLLAMA_BASE_URL=... JWT_SECRET_KEY=... python -m scripts.backfill_knowledge_chunks
    DATABASE_URL=... ... python -m scripts.backfill_knowledge_chunks --yes  # 확인 프롬프트 생략
"""

import argparse
import asyncio
import logging
from collections.abc import Callable
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.models.interview_practice_session import InterviewPracticeSession
from app.db.models.interview_practice_turn import InterviewPracticeTurn
from app.db.models.interview_review import InterviewReview
from app.db.models.quiz import Quiz
from app.db.models.study_message import StudyMessage
from app.db.models.study_session import StudySession
from app.db.session import to_asyncpg_url
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _redact_database_url(url: str) -> str:
    """확인 프롬프트에 대상 DB를 보여줄 때 비밀번호가 터미널 히스토리/로그에
    남지 않도록 호스트:포트/DB이름만 남긴다."""
    parsed = urlsplit(url)
    host = parsed.hostname or "?"
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path.lstrip("/") or "?"
    return f"{host}{port}/{database}"


def _confirm_before_running(database_url: str, ask: Callable[[str], str] = input) -> bool:
    """실수로 프로덕션 DATABASE_URL을 물고 있는 셸에서 이 스크립트를 돌리면
    전체 이력을 훑으며 Ollama 임베딩 API를 순차로 수천 번 호출할 수 있다 -
    돌리기 전에 대상 DB를 명시적으로 보여주고 확인받는다."""
    target = _redact_database_url(database_url)
    answer = ask(
        f"다음 DB의 전체 이력을 재색인합니다: {target}\n"
        "실수로 프로덕션을 가리키고 있지 않은지 확인하세요. 계속하시겠습니까? [y/N]: "
    )
    return answer.strip().lower() == "y"


async def backfill_all_content(session: AsyncSession, rag_service: RagService) -> tuple[int, int, int, int]:
    """세션/RagService가 이미 준비된 뒤의 실제 색인 로직 - 엔진/세션 생성 및
    확인 프롬프트와 분리해 테스트 가능하게 한다."""
    message_rows = await session.execute(
        select(StudyMessage, StudySession.user_id).join(StudySession, StudyMessage.session_id == StudySession.id)
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

    # source_study_session_id로 만든 퀴즈는 원본이 이미 study_message 쪽에
    # 색인돼 있으므로 제외한다 - 직접 붙여넣은(source_text가 채워진) 퀴즈만 대상.
    quiz_rows = await session.execute(select(Quiz).where(Quiz.source_text.is_not(None)))
    quizzes = list(quiz_rows.scalars().all())
    for index, quiz in enumerate(quizzes, start=1):
        assert quiz.source_text is not None
        await rag_service.index_content(
            user_id=quiz.user_id,
            source_type="quiz_source",
            source_id=quiz.id,
            content=quiz.source_text,
        )
        logger.info("[quiz_source %d/%d] 색인 완료: %s", index, len(quizzes), quiz.id)

    # 아직 답변 안 한 턴은 애초에 색인 대상이 아니다 (submit_answer가 답변이
    # 달릴 때만 색인한다).
    turn_rows = await session.execute(
        select(InterviewPracticeTurn, InterviewPracticeSession.user_id)
        .join(InterviewPracticeSession, InterviewPracticeTurn.session_id == InterviewPracticeSession.id)
        .where(InterviewPracticeTurn.answer.is_not(None))
    )
    turns = turn_rows.all()
    for index, (turn, user_id) in enumerate(turns, start=1):
        await rag_service.index_content(
            user_id=user_id,
            source_type="interview_practice_turn",
            source_id=turn.id,
            content=f"질문: {turn.question}\n답변: {turn.answer}",
        )
        logger.info("[interview_practice_turn %d/%d] 색인 완료: %s", index, len(turns), turn.id)

    return len(messages), len(reviews), len(quizzes), len(turns)


async def backfill(*, skip_confirmation: bool = False) -> None:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다.")

    if not skip_confirmation and not _confirm_before_running(settings.database_url):
        logger.info("취소되었습니다.")
        return

    engine = create_async_engine(to_asyncpg_url(settings.database_url))
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    ollama_service = OllamaService(base_url=settings.ollama_base_url)

    try:
        async with session_factory() as session:
            rag_service = RagService(session=session, ollama_service=ollama_service, settings=settings)
            message_count, review_count, quiz_count, turn_count = await backfill_all_content(session, rag_service)

        logger.info(
            "백필 완료: study_message %d건, interview_review %d건, quiz_source %d건, "
            "interview_practice_turn %d건",
            message_count,
            review_count,
            quiz_count,
            turn_count,
        )
    finally:
        await engine.dispose()
        await ollama_service.aclose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="확인 프롬프트 없이 바로 실행한다 (cron/CI 등 비대화형 환경용).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(backfill(skip_confirmation=args.yes))
