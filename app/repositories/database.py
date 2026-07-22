import logging

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_db_pool(database_url: str | None) -> None:
    """앱 시작 시 DB 커넥션 풀을 생성한다. DATABASE_URL이 없으면 건너뛴다."""
    global _pool
    if not database_url:
        logger.warning("DATABASE_URL이 설정되지 않아 DB 커넥션 풀을 생성하지 않습니다.")
        return
    _pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)


async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def keep_supabase_alive() -> None:
    """Supabase DB에 SELECT 1 쿼리를 날려 7일 비활성화 정지를 방지한다."""
    if _pool is None:
        logger.warning("DB 커넥션 풀이 초기화되지 않아 ping을 건너뜁니다.")
        return
    try:
        async with _pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")
        logger.info("[Supabase Ping] DB가 성공적으로 살아있음을 확인했습니다.")
    except Exception:
        logger.exception("[Supabase Ping] DB 통신 실패")


async def check_db_health() -> bool:
    """readiness 체크용: 풀에서 커넥션을 얻어 간단한 쿼리를 수행할 수 있는지 확인한다."""
    if _pool is None:
        return False
    try:
        async with _pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")
        return True
    except Exception:
        logger.exception("DB 헬스체크 실패")
        return False
