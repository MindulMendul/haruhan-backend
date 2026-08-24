import logging

from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db.session import cleanup_expired_refresh_tokens, keep_supabase_alive
from app.services.rag_backfill_service import run_scheduled_rag_backfill

logger = logging.getLogger("haruhan")

scheduler = AsyncIOScheduler()


def _log_missed_or_failed_job(event: JobExecutionEvent) -> None:
    """APScheduler는 misfire_grace_time을 넘겨 건너뛴 job이나 예외를 던진 job을
    기본적으로 자기 자신의 로거(`apscheduler.scheduler`)에 WARNING/에러로만 남기고
    지나간다 - 이 앱은 Sentry 같은 별도 에러 트래킹 없이 로그 레벨로 문제를
    감지하는 구조라(다른 곳의 logger.exception(...) 패턴과 동일), 하루 한 번만
    도는 이 잡들(특히 keep_supabase_alive - 7일 연속 놓치면 Supabase가 자동
    정지된다)이 놓치거나 실패해도 눈에 띄는 로그가 없으면 알아챌 방법이 없다.
    이 리스너로 이 앱의 로거에도 명시적으로 남긴다."""
    if event.code == EVENT_JOB_MISSED:
        logger.error("[스케줄러] job 실행을 건너뜀 (misfire): job_id=%s", event.job_id)
    else:
        logger.error(
            "[스케줄러] job 실행 실패: job_id=%s", event.job_id, exc_info=event.exception
        )


def setup_scheduler_jobs() -> None:
    scheduler.add_listener(_log_missed_or_failed_job, EVENT_JOB_MISSED | EVENT_JOB_ERROR)
    # misfire_grace_time=None: 이 job들은 하루에 한 번, 분 단위로 정확할 필요
    # 없이 그냥 "하루 한 번 도는 것"이 중요한 유지보수성 작업이다. AsyncIOScheduler
    # 는 FastAPI/uvicorn과 같은 이벤트 루프를 공유하는데, 기본 misfire_grace_time
    # 이 1초라서 예정된 실행 시각에 이벤트 루프가 요청 처리/GC 등으로 1초 이상
    # 밀리기만 해도(평범한 트래픽에서 충분히 있을 수 있는 일) 그날 실행을
    # 통째로 건너뛰고 조용히 넘어간다 - keep_supabase_alive처럼 "7일 연속 놓치면
    # Supabase가 자동 정지된다"는 걸 막으려고 만든 job이 정작 이 좁은 기본
    # grace window 때문에 놓치기 쉬운 상태였다. None으로 두면 실행 시각이
    # 아무리 늦어도(다음날 트리거 전까지는) 건너뛰지 않고 그냥 실행한다.
    scheduler.add_job(keep_supabase_alive, "cron", hour=3, minute=0, misfire_grace_time=None)
    scheduler.add_job(cleanup_expired_refresh_tokens, "cron", hour=4, minute=0, misfire_grace_time=None)
    scheduler.add_job(run_scheduled_rag_backfill, "cron", hour=5, minute=0, misfire_grace_time=None)
