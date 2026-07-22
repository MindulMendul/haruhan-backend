from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.repositories.database import keep_supabase_alive

scheduler = AsyncIOScheduler()


def setup_scheduler_jobs() -> None:
    scheduler.add_job(keep_supabase_alive, "cron", hour=3, minute=0)
