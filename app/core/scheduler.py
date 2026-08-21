from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import cleanup_expired_refresh_tokens, keep_supabase_alive

scheduler = AsyncIOScheduler()


def setup_scheduler_jobs() -> None:
    scheduler.add_job(keep_supabase_alive, "cron", hour=3, minute=0)
    scheduler.add_job(cleanup_expired_refresh_tokens, "cron", hour=4, minute=0)
