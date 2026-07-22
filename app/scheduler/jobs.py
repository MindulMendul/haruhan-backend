from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import ping_database

scheduler = BackgroundScheduler()
scheduler.add_job(ping_database, "cron", hour=3, minute=0)


def start_scheduler() -> None:
    scheduler.start()
    # 서버 기동 시 즉시 한번 DB 찌르기
    ping_database()


def shutdown_scheduler() -> None:
    scheduler.shutdown()
