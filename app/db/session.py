import psycopg2

from app.core.config import settings
from app.core.logging import logger


def ping_database() -> None:
    """Supabase DB에 SELECT 1 쿼리를 날려 7일 비활성화 정지를 방지"""
    if not settings.database_url:
        logger.warning("DATABASE_URL이 설정되지 않았습니다.")
        return
    try:
        conn = psycopg2.connect(settings.database_url)
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.close()
        conn.close()
        logger.info("🟢 [Supabase Ping] DB가 성공적으로 살아있음을 확인했습니다.")
    except Exception as e:
        logger.error(f"🔴 [Supabase Ping] DB 통신 실패: {e}")
