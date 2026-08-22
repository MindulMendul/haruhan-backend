import asyncio
import os
import tempfile
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import session as db_session


def _temp_sqlite_url() -> str:
    """init_engine()은 pool_size/max_overflow를 그대로 create_async_engine에
    넘기는데, sqlite+aiosqlite의 :memory: URL은 기본 poolclass가 StaticPool이라
    이 kwarg들을 받지 않는다 - 파일 기반 sqlite는 AsyncAdaptedQueuePool을 써서
    받아들이므로(운영의 Postgres와 같은 풀링 구성), 임시 파일 경로를 쓴다.
    """
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    return f"sqlite+aiosqlite:///{path}"

# 이 파일은 db/session.py가 "엔진이 아직 초기화 안 됐을 때" 안전하게 동작하는지를
# 확인한다. 다른 테스트는 전부 conftest.py의 db_session_factory 픽스처로 별도 DB를
# 쓰고 get_db()를 오버라이드하기 때문에, 앱의 실제 DATABASE_URL이 테스트 환경에서는
# 항상 비어 있어 이 모듈 전역 상태는 테스트 전체에서 미초기화 상태로 남는다.


def test_to_asyncpg_url_converts_known_postgres_schemes():
    assert (
        db_session.to_asyncpg_url("postgres://u:p@host/db") == "postgresql+asyncpg://u:p@host/db"
    )
    assert (
        db_session.to_asyncpg_url("postgresql://u:p@host/db")
        == "postgresql+asyncpg://u:p@host/db"
    )
    assert (
        db_session.to_asyncpg_url("postgresql+asyncpg://u:p@host/db")
        == "postgresql+asyncpg://u:p@host/db"
    )


def test_to_asyncpg_url_leaves_other_schemes_unchanged():
    assert db_session.to_asyncpg_url("sqlite+aiosqlite:///./x.db") == "sqlite+aiosqlite:///./x.db"


def test_init_engine_without_database_url_leaves_factory_uninitialized(caplog):
    async def _run():
        await db_session.init_engine(None)

    with caplog.at_level("WARNING", logger="app.db.session"):
        asyncio.run(_run())
    assert "DATABASE_URL이 설정되지 않아" in caplog.text


def test_get_db_raises_when_uninitialized():
    async def _run():
        got_error = False
        try:
            async for _ in db_session.get_db():
                pass
        except RuntimeError:
            got_error = True
        assert got_error

    asyncio.run(_run())


def test_get_db_yields_working_session_when_initialized():
    async def _check():
        from sqlalchemy import text

        async for session in db_session.get_db():
            result = await session.execute(text("SELECT 1"))
            assert result.scalar_one() == 1
            break

    asyncio.run(_with_initialized_engine(_check))


def test_check_db_health_returns_false_when_uninitialized():
    assert asyncio.run(db_session.check_db_health()) is False


def test_keep_supabase_alive_warns_when_uninitialized(caplog):
    with caplog.at_level("WARNING", logger="app.db.session"):
        asyncio.run(db_session.keep_supabase_alive())
    assert "DB 엔진이 초기화되지 않아 ping을 건너뜁니다" in caplog.text


def test_cleanup_expired_refresh_tokens_warns_when_uninitialized(caplog):
    with caplog.at_level("WARNING", logger="app.db.session"):
        asyncio.run(db_session.cleanup_expired_refresh_tokens())
    assert "DB 엔진이 초기화되지 않아 refresh token 정리를 건너뜁니다" in caplog.text


def test_enable_sqlite_foreign_keys_noop_for_non_sqlite_dialect():
    class _FakeDialect:
        name = "postgresql"

    class _FakeEngine:
        dialect = _FakeDialect()

    # sync_engine에 접근하면 바로 에러가 나야 정상인 가짜 엔진을 넘겨서, sqlite가
    # 아닐 때는 dialect.name만 확인하고 조용히 리턴하는지(이벤트 리스너를 걸려고
    # sync_engine에 접근하지 않는지) 검증한다.
    db_session.enable_sqlite_foreign_keys(_FakeEngine())


async def _with_initialized_engine(coro):
    """init_engine()이 만드는 모듈 전역 _engine/_session_factory를 테스트 동안만
    실제 SQLite 엔진으로 채웠다가, 다른 테스트(엔진 미초기화 케이스 포함)에
    영향을 주지 않도록 반드시 되돌린다."""
    url = _temp_sqlite_url()
    db_path = url.removeprefix("sqlite+aiosqlite://")
    await db_session.init_engine(url)
    try:
        import app.db.models  # noqa: F401  (Base.metadata에 테이블 등록)
        from app.db.base import Base

        async with db_session._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        await coro()
    finally:
        await db_session.close_engine()
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_init_engine_and_close_engine_round_trip():
    url = _temp_sqlite_url()
    db_path = url.removeprefix("sqlite+aiosqlite://")

    async def _run():
        await db_session.init_engine(url)
        assert db_session._engine is not None
        assert db_session._session_factory is not None

        async with db_session._session_factory() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT 1"))

        await db_session.close_engine()
        assert db_session._engine is None
        assert db_session._session_factory is None

    try:
        asyncio.run(_run())
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_check_db_health_returns_true_when_initialized():
    async def _check():
        assert await db_session.check_db_health() is True

    asyncio.run(_with_initialized_engine(_check))


def test_check_db_health_returns_false_on_query_error(monkeypatch):
    async def _check():
        monkeypatch.setattr(AsyncSession, "execute", AsyncMock(side_effect=RuntimeError("boom")))
        assert await db_session.check_db_health() is False

    asyncio.run(_with_initialized_engine(_check))


def test_keep_supabase_alive_logs_success_when_initialized(caplog):
    async def _check():
        with caplog.at_level("INFO", logger="app.db.session"):
            await db_session.keep_supabase_alive()
        assert "DB가 성공적으로 살아있음을 확인했습니다" in caplog.text

    asyncio.run(_with_initialized_engine(_check))


def test_keep_supabase_alive_logs_error_on_query_failure(monkeypatch, caplog):
    async def _check():
        monkeypatch.setattr(AsyncSession, "execute", AsyncMock(side_effect=RuntimeError("boom")))
        with caplog.at_level("ERROR", logger="app.db.session"):
            await db_session.keep_supabase_alive()
        assert "[Supabase Ping] DB 통신 실패" in caplog.text

    asyncio.run(_with_initialized_engine(_check))


def test_cleanup_expired_refresh_tokens_logs_deleted_count_when_initialized(caplog):
    async def _check():
        with caplog.at_level("INFO", logger="app.db.session"):
            await db_session.cleanup_expired_refresh_tokens()
        assert "만료된 토큰" in caplog.text

    asyncio.run(_with_initialized_engine(_check))


def test_cleanup_expired_refresh_tokens_logs_error_on_failure(monkeypatch, caplog):
    async def _check():
        monkeypatch.setattr(AsyncSession, "execute", AsyncMock(side_effect=RuntimeError("boom")))
        with caplog.at_level("ERROR", logger="app.db.session"):
            await db_session.cleanup_expired_refresh_tokens()
        assert "[Refresh Token 정리] 실패" in caplog.text

    asyncio.run(_with_initialized_engine(_check))
