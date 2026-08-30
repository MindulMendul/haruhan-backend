import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.clock import utcnow_naive
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository

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


def enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    """SQLite는 기본적으로 외래키 제약을 검사하지 않아서 모델에 걸어둔
    ON DELETE CASCADE/SET NULL이 조용히 무시된다 (Postgres는 기본으로 검사하므로
    프로덕션에서는 원래도 문제없었음). 연결마다 PRAGMA로 켜서 SQLite를 쓰는
    테스트/로컬 개발에서도 같은 cascade 동작을 보장한다. sqlite가 아니면 아무것도
    하지 않는다.
    """
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def init_engine(database_url: str | None) -> None:
    """앱 시작 시 DB 엔진/세션 팩토리를 만든다. DATABASE_URL이 없으면 건너뛴다."""
    global _engine, _session_factory
    if not database_url:
        logger.warning("DATABASE_URL이 설정되지 않아 DB 엔진을 생성하지 않습니다.")
        return
    # pool_pre_ping: 커넥션을 풀에서 꺼내 쓰기 직전에 가벼운 SELECT 1로 살아있는지
    # 확인한다. Supabase 같은 관리형 Postgres는 커넥션 풀러(pgbouncer 등)가 유휴
    # 커넥션을 서버 쪽에서 조용히 끊는 경우가 흔한데, keep_supabase_alive()는 하루
    # 한 번(APScheduler cron)만 돌아 DB 자체의 7일 자동 정지만 막을 뿐, 그보다
    # 훨씬 잦은 주기로 개별 풀 커넥션이 끊기는 것까지는 막지 못한다. 이게 없으면
    # 끊긴 커넥션으로 첫 쿼리를 시도한 요청이 그대로 500으로 실패한다 - pre_ping을
    # 켜면 SQLAlchemy가 끊긴 커넥션을 감지해 조용히 새 커넥션으로 교체해준다.
    _engine = create_async_engine(
        to_asyncpg_url(database_url), pool_size=5, max_overflow=5, pool_pre_ping=True
    )
    enable_sqlite_foreign_keys(_engine)
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


async def cleanup_expired_refresh_tokens() -> None:
    """만료된 refresh token을 주기적으로 정리해 테이블이 무한정 커지는 것을 막는다."""
    if _session_factory is None:
        logger.warning("DB 엔진이 초기화되지 않아 refresh token 정리를 건너뜁니다.")
        return
    try:
        async with _session_factory() as session:
            deleted = await RefreshTokenRepository(session).delete_expired()
        logger.info("[Refresh Token 정리] 만료된 토큰 %d개 삭제", deleted)
    except Exception:
        logger.exception("[Refresh Token 정리] 실패")


async def cleanup_stale_guest_accounts() -> None:
    """활성 refresh token이 하나도 남지 않아 재로그인 자체가 불가능해진(=본인도
    다시 접근할 수 없는) 게스트 계정을 정리한다. 학습챗/퀴즈/면접연습/면접복기
    데이터가 계속 쌓이기만 하고 아무도 다시 볼 수 없는 채로 무기한 보관되는
    것을 막는다."""
    if _session_factory is None:
        logger.warning("DB 엔진이 초기화되지 않아 게스트 계정 정리를 건너뜁니다.")
        return
    try:
        async with _session_factory() as session:
            deleted = await UserRepository(session).delete_stale_guests(utcnow_naive())
        logger.info("[게스트 계정 정리] 접근 불가능해진 게스트 계정 %d개 삭제", deleted)
    except Exception:
        logger.exception("[게스트 계정 정리] 실패")


async def check_db_health(timeout_seconds: float) -> bool:
    """readiness 체크용: 세션을 열어 간단한 쿼리를 수행할 수 있는지 확인한다.

    이 세션이 커넥션 풀에서 커넥션을 새로 얻어야 하면 asyncpg 기본 연결
    타임아웃(60초)을 그대로 물려받는다 - DB가 완전히 죽은 게 아니라 응답만
    느려지는 상황에서는 이 확인 하나가 최대 60초까지 걸릴 수 있다 -
    core/health.py의 check_redis_health/check_ollama_health와 같은 이유로
    health_check_timeout_seconds로 짧은 상한을 건다.
    """
    if _session_factory is None:
        return False
    try:
        async with _session_factory() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=timeout_seconds)
        return True
    except Exception:
        logger.exception("DB 헬스체크 실패")
        return False
