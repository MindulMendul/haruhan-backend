import asyncio
import logging
import urllib.parse
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
    """Supabase 등에서 주는 postgresql:// 접속 문자열을 SQLAlchemy async 드라이버 스킴으로 바꾼다.

    SQLAlchemy의 asyncpg 방언(`create_connect_args`)은 URL 쿼리 문자열에 있는
    키를 전부 그대로 `asyncpg.connect()`의 키워드 인자로 넘긴다. 그런데
    `sslmode=`는 libpq/psql/psycopg2 계열(그리고 Supabase 등 관리형 Postgres가
    "SSL 필수" 접속 문자열을 안내할 때 흔히 붙여주는 바로 그 파라미터)의
    관례일 뿐, asyncpg의 실제 `connect()` 시그니처에는 그런 키워드 인자가
    없다(`ssl`만 있음) - `sslmode=require`가 붙은 DATABASE_URL로 연결을
    시도하면 네트워크 I/O 전에 `TypeError: connect() got an unexpected
    keyword argument 'sslmode'`가 그대로 난다는 것을 실제 asyncpg 0.31.0로
    직접 재현해 확인했다. 이 예외는 이 앱이 세심하게 다뤄온 IntegrityError/
    StaleDataError 같은 종류가 아니라 완전히 다른 계층(DB 드라이버 자체의
    키워드 인자 검증)에서 나서, 매 요청마다(로그인/회원가입 등 DB를 만지는
    모든 경로) 처리되지 않은 예외로 500이 된다 - `keep_supabase_alive()`가
    부팅 시점 핑을 넓은 except로 감싸둔 덕에 앱 자체는 뜨지만, 그 뒤 실제
    요청은 전부 실패한다. asyncpg 내부적으로는 `ssl=` 값이 문자열이면
    `SSLMode.parse()`로 해석하는데, 이게 정확히 libpq의 `sslmode` 값
    어휘(disable/allow/prefer/require/verify-ca/verify-full)와 같다는 것도
    asyncpg 소스(`connect_utils.py`)로 확인했다 - 즉 `sslmode` 쿼리 키를
    `ssl`로 이름만 바꾸면 값 해석은 그대로 유지된다(의미 재해석이 아니라
    순수 키 이름 교정). `ssl=require`로 바꾼 뒤 실제로 연결을 시도해보면
    (서버가 없는 포트라도) `TypeError`가 아니라 `ConnectionRefusedError`로
    넘어간다는 것까지 재현해 확인했다 - 키워드 인자 검증은 통과했다는 뜻.
    """
    if url.startswith("postgresql+asyncpg://"):
        pass
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    elif url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://") :]
    else:
        return url
    return _rename_sslmode_query_param(url)


def _rename_sslmode_query_param(url: str) -> str:
    split = urllib.parse.urlsplit(url)
    query_pairs = urllib.parse.parse_qsl(split.query, keep_blank_values=True)
    if not any(key == "sslmode" for key, _ in query_pairs):
        # 대부분의 접속 문자열엔 sslmode가 아예 없다 - 그런 경우는 쿼리 문자열을
        # 굳이 다시 인코딩하지 않고 원본 그대로 돌려준다(불필요한 변형 방지).
        return url
    renamed_pairs = [("ssl" if key == "sslmode" else key, value) for key, value in query_pairs]
    return urllib.parse.urlunsplit(split._replace(query=urllib.parse.urlencode(renamed_pairs)))


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


def _connect_args_for(resolved_url: str) -> dict[str, Any]:
    """이 접속 문자열(to_asyncpg_url()을 거친 뒤)에 맞는 create_async_engine()의
    connect_args를 고른다.

    이 앱의 모든 모델은 updated_at 등에 onupdate=func.now()(DB 서버 자신의 클럭)를
    쓰는데, study_session_repository.touch() 같은 곳은 그 대신 utcnow_naive()
    (파이썬 쪽 진짜 UTC 클럭)로 같은 컬럼을 직접 덮어쓴다 - 즉 같은 컬럼이
    호출부에 따라 서로 다른 두 클럭 중 하나로 채워진다. func.now()가 실제로
    UTC를 내놓는다는 보장은, 이 접속 문자열이 가리키는 Postgres 세션의 timezone
    GUC가 UTC라는 가정에 의존하는데, 이 앱은 그 DB 인스턴스를 직접 프로비저닝하지
    않고(Supabase 등 관리형 서비스나 운영자가 별도로 준비) 그 GUC 기본값을
    확인/강제하는 코드가 어디에도 없었다. 로컬 Postgres에 timezone='Asia/Seoul'을
    설정해 재현한 결과: 같은 순간 touch()가 쓴 값은 정확한 UTC인데 update_title()이
    기댄 func.now()는 9시간 앞선(=한국 표준시로 읽힌 "지역 시각"이 그대로 naive
    UTC인 것처럼 저장된) 값이 나왔다 - list_for_user()의 "최근 순" 정렬이 방금
    채팅한 세션보다 그보다 먼저 이름만 바꾼 세션을 위로 올리고, API가 UtcDatetime
    으로 그 값에 그대로 "Z"를 붙여 내려보내(schemas/validators.py 참고) 프론트에는
    몇 시간 뒤 미래 시각으로 보인다. server_settings로 이 세션의 timezone을
    명시적으로 UTC 고정해 외부 DB의 기본 설정과 무관하게 func.now()가 항상 진짜
    UTC를 내놓도록 보장한다. SQLite(테스트/로컬)는 CURRENT_TIMESTAMP가 세션
    설정과 무관하게 항상 UTC라 이 문제 자체가 없고, aiosqlite의 connect()는
    server_settings 키워드를 아예 모르므로(TypeError) Postgres URL일 때만
    넘긴다."""
    if resolved_url.startswith("postgresql+asyncpg://"):
        return {"server_settings": {"timezone": "UTC"}}
    return {}


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
    resolved_url = to_asyncpg_url(database_url)
    _engine = create_async_engine(
        resolved_url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        connect_args=_connect_args_for(resolved_url),
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
