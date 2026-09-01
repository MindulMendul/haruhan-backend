import asyncio
import os
import tempfile
import urllib.parse
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


def test_to_asyncpg_url_renames_sslmode_query_param_to_ssl():
    """SQLAlchemy의 asyncpg 방언은 URL 쿼리 문자열의 키를 전부 그대로
    asyncpg.connect()의 키워드 인자로 넘긴다 - Supabase 등 관리형 Postgres가
    "SSL 필수" 접속 문자열에 흔히 붙여주는 `sslmode=`는 libpq 계열 관례일 뿐
    asyncpg.connect()에는 그런 키워드 인자가 없어(`ssl`만 있음)
    `TypeError: unexpected keyword argument 'sslmode'`로 그대로 터진다(직접
    재현해 확인함). asyncpg는 `ssl=` 값이 문자열이면 libpq와 같은 어휘
    (disable/allow/prefer/require/verify-ca/verify-full)로 해석하므로, 키
    이름만 `ssl`로 바꾸면 의미는 그대로 유지된다."""
    assert (
        db_session.to_asyncpg_url("postgresql://u:p@host/db?sslmode=require")
        == "postgresql+asyncpg://u:p@host/db?ssl=require"
    )
    assert (
        db_session.to_asyncpg_url("postgres://u:p@host/db?sslmode=disable")
        == "postgresql+asyncpg://u:p@host/db?ssl=disable"
    )


def test_to_asyncpg_url_preserves_other_query_params_alongside_sslmode():
    result = db_session.to_asyncpg_url("postgresql://u:p@host/db?sslmode=require&target_session_attrs=read-write")
    parsed = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(result).query))
    assert parsed == {"ssl": "require", "target_session_attrs": "read-write"}


def test_to_asyncpg_url_leaves_query_string_unchanged_when_no_sslmode():
    assert (
        db_session.to_asyncpg_url("postgresql://u:p@host/db?application_name=haruhan")
        == "postgresql+asyncpg://u:p@host/db?application_name=haruhan"
    )


def test_to_asyncpg_url_with_sslmode_actually_passes_asyncpg_keyword_validation():
    """단순히 문자열 치환이 맞는지가 아니라, 실제로 asyncpg.connect()의 키워드
    인자 검증을 통과하는지까지 확인한다 - 서버가 없는 포트로 연결을 시도했을 때
    (네트워크 I/O가 실제로 일어나기 전 단계인) TypeError가 아니라
    ConnectionRefusedError/OSError로 넘어가야 키워드 인자 자체는 문제없다는 뜻이다."""
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _run() -> BaseException | None:
        engine = create_async_engine(
            db_session.to_asyncpg_url("postgresql://u:p@127.0.0.1:1/db?sslmode=require")
        )
        try:
            async with engine.connect():
                pass
        except Exception as exc:  # noqa: BLE001 - 정확히 어떤 예외인지가 이 테스트의 확인 대상
            return exc
        finally:
            await engine.dispose()
        return None

    exc = asyncio.run(_run())
    assert exc is not None
    assert not isinstance(exc, TypeError)


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


def test_init_engine_enables_pool_pre_ping():
    """관리형 Postgres(Supabase 등)의 커넥션 풀러가 유휴 커넥션을 조용히 끊어도,
    풀에서 꺼내 쓰기 전에 SQLAlchemy가 자동으로 감지하고 재연결하도록
    pool_pre_ping이 켜져 있는지 확인한다 - 없으면 끊긴 커넥션으로 첫 쿼리를
    시도한 요청이 그대로 500으로 실패한다."""

    async def _check():
        assert db_session._engine.pool._pre_ping is True

    asyncio.run(_with_initialized_engine(_check))


# 202라운드: 모든 모델의 updated_at 등은 onupdate=func.now()(Postgres 서버 자신의
# 클럭)를 쓰는데, study_session_repository.touch() 같은 곳은 같은 컬럼을
# utcnow_naive()(파이썬 쪽 진짜 UTC 클럭)로 직접 덮어쓴다 - func.now()가 실제로
# UTC를 내놓는 건 이 접속 문자열이 가리키는 Postgres 세션의 timezone GUC가
# UTC일 때뿐인데, 이 앱은 그 DB 인스턴스를 직접 프로비저닝하지 않아(Supabase 등
# 관리형 서비스) 그 기본값을 확인/강제하는 코드가 없었다. 로컬 Postgres에
# timezone='Asia/Seoul'을 설정해 실제로 재현한 결과, 같은 순간 touch()가 쓴
# 값은 정확한 UTC인데 update_title()이 기댄 func.now()는 9시간 앞선 값이 나와
# list_for_user()의 "최근 순" 정렬이 뒤집히고 API 응답의 UtcDatetime 직렬화가
# 그 값에 그대로 "Z"를 붙여 프론트에 몇 시간 뒤 미래 시각으로 보이는 것까지
# 확인했다(db/session.py의 _connect_args_for() docstring 참고).
def test_connect_args_for_pins_utc_timezone_for_postgres_url():
    assert db_session._connect_args_for("postgresql+asyncpg://u:p@host/db") == {
        "server_settings": {"timezone": "UTC"}
    }


def test_connect_args_for_is_empty_for_sqlite_url():
    """aiosqlite의 connect()는 server_settings 키워드를 아예 모르므로(TypeError),
    SQLite URL에는 이 connect_args를 넘기면 안 된다."""
    assert db_session._connect_args_for("sqlite+aiosqlite:///./x.db") == {}


def test_init_engine_pins_utc_timezone_via_connect_args(monkeypatch):
    """init_engine()이 실제로 to_asyncpg_url()을 거친 URL을 _connect_args_for()에
    넘겨 create_async_engine()의 connect_args로 전달하는지, 엔드투엔드로 확인한다."""
    captured = {}
    original_create_async_engine = db_session.create_async_engine

    def _capturing_create_async_engine(url, **kwargs):
        captured["connect_args"] = kwargs.get("connect_args")
        return original_create_async_engine(url, **kwargs)

    monkeypatch.setattr(db_session, "create_async_engine", _capturing_create_async_engine)

    async def _run():
        await db_session.init_engine("postgresql://u:p@host/db")
        await db_session.close_engine()

    asyncio.run(_run())
    assert captured["connect_args"] == {"server_settings": {"timezone": "UTC"}}


def test_check_db_health_returns_false_when_uninitialized():
    assert asyncio.run(db_session.check_db_health(3.0)) is False


def test_keep_supabase_alive_warns_when_uninitialized(caplog):
    with caplog.at_level("WARNING", logger="app.db.session"):
        asyncio.run(db_session.keep_supabase_alive())
    assert "DB 엔진이 초기화되지 않아 ping을 건너뜁니다" in caplog.text


def test_cleanup_expired_refresh_tokens_warns_when_uninitialized(caplog):
    with caplog.at_level("WARNING", logger="app.db.session"):
        asyncio.run(db_session.cleanup_expired_refresh_tokens())
    assert "DB 엔진이 초기화되지 않아 refresh token 정리를 건너뜁니다" in caplog.text


def test_cleanup_stale_guest_accounts_warns_when_uninitialized(caplog):
    with caplog.at_level("WARNING", logger="app.db.session"):
        asyncio.run(db_session.cleanup_stale_guest_accounts())
    assert "DB 엔진이 초기화되지 않아 게스트 계정 정리를 건너뜁니다" in caplog.text


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
        assert await db_session.check_db_health(3.0) is True

    asyncio.run(_with_initialized_engine(_check))


def test_check_db_health_returns_false_on_query_error(monkeypatch):
    async def _check():
        monkeypatch.setattr(AsyncSession, "execute", AsyncMock(side_effect=RuntimeError("boom")))
        assert await db_session.check_db_health(3.0) is False

    asyncio.run(_with_initialized_engine(_check))


def test_check_db_health_returns_false_when_query_is_slower_than_timeout(monkeypatch):
    """DB가 완전히 죽은 게 아니라 응답만 느려지는 상황(연결 풀러 문제 등)에서는
    이 쿼리 하나가 asyncpg 기본 연결 타임아웃(60초)까지 걸릴 수 있다 - readiness
    probe는 빠르게 답해야 의미가 있으므로, health_check_timeout_seconds로
    실제로 짧은 상한이 걸리는지 확인한다."""

    async def _slow_execute(*args, **kwargs):
        await asyncio.sleep(1.0)

    async def _check():
        monkeypatch.setattr(AsyncSession, "execute", _slow_execute)
        loop = asyncio.get_running_loop()
        start = loop.time()
        result = await db_session.check_db_health(0.05)
        elapsed = loop.time() - start
        assert result is False
        assert elapsed < 1.0

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


def test_cleanup_stale_guest_accounts_logs_deleted_count_when_initialized(caplog):
    async def _check():
        with caplog.at_level("INFO", logger="app.db.session"):
            await db_session.cleanup_stale_guest_accounts()
        assert "게스트 계정" in caplog.text

    asyncio.run(_with_initialized_engine(_check))


def test_cleanup_stale_guest_accounts_logs_error_on_failure(monkeypatch, caplog):
    async def _check():
        monkeypatch.setattr(AsyncSession, "execute", AsyncMock(side_effect=RuntimeError("boom")))
        with caplog.at_level("ERROR", logger="app.db.session"):
            await db_session.cleanup_stale_guest_accounts()
        assert "[게스트 계정 정리] 실패" in caplog.text

    asyncio.run(_with_initialized_engine(_check))
