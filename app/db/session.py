import logging
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def to_asyncpg_url(url: str) -> str:
    """Supabase 등에서 주는 postgresql:// 접속 문자열을 SQLAlchemy async 드라이버 스킴으로 바꾼다."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url[len("postgres://") :]
    return url


async def init_engine(database_url: str | None) -> None:
    """앱 시작 시 DB 엔진/세션 팩토리를 만든다. DATABASE_URL이 없으면 건너뛴다."""
    global _engine, _session_factory
    if not database_url:
        logger.warning("DATABASE_URL이 설정되지 않아 DB 엔진을 생성하지 않습니다.")
        return
    _engine = create_async_engine(to_asyncpg_url(database_url), pool_size=5, max_overflow=5)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def close_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_db() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("DB 엔진이 초기화되지 않았습니다 (DATABASE_URL 설정 확인).")
    async with _session_factory() as session:
        yield session


async def keep_supabase_alive() -> None:
    """Supabase DB에 SELECT 1 쿼리를 날려 7일 비활성화 정지를 방지한다."""
    if _session_factory is None:
        logger.warning("DB 엔진이 초기화되지 않아 ping을 건너뜁니다.")
        return
    try:
        async with _session_factory() as session:
            await session.execute(text("SELECT 1"))
        logger.info("[Supabase Ping] DB가 성공적으로 살아있음을 확인했습니다.")
    except Exception:
        logger.exception("[Supabase Ping] DB 통신 실패")


async def check_db_health() -> bool:
    """readiness 체크용: 세션을 열어 간단한 쿼리를 수행할 수 있는지 확인한다."""
    if _session_factory is None:
        return False
    try:
        async with _session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("DB 헬스체크 실패")
        return False
