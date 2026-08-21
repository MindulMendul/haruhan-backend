import asyncio

from app.db import session as db_session

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
