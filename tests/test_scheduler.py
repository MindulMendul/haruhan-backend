from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED, JobExecutionEvent

from app.core.scheduler import _log_missed_or_failed_job


def test_missed_job_is_logged_at_error_level(caplog):
    """APScheduler는 misfire_grace_time을 넘겨 건너뛴 job을 기본적으로 자기
    자신의 로거(`apscheduler.scheduler`)에만 남긴다 - 이 앱은 Sentry 같은 별도
    에러 트래킹 없이 로그 레벨로 문제를 감지하는 구조라, 이 앱 자신의
    로거("haruhan")에도 눈에 띄게(ERROR) 남겨야 놓친 걸 알아챌 수 있다."""
    event = JobExecutionEvent(
        code=EVENT_JOB_MISSED,
        job_id="keep_supabase_alive",
        jobstore="default",
        scheduled_run_time=None,
    )
    with caplog.at_level("ERROR", logger="haruhan"):
        _log_missed_or_failed_job(event)

    assert any(
        record.levelname == "ERROR" and "keep_supabase_alive" in record.message
        for record in caplog.records
    )


def test_failed_job_is_logged_at_error_level_with_exception(caplog):
    """job이 예외를 던지고 실행 자체는 실패한 경우도(misfire와는 다른 코드) 같은
    방식으로 이 앱의 로거에 남겨야 한다 - 예외 정보(exc_info)도 함께 남아야
    스택트레이스로 원인을 바로 알 수 있다."""
    boom = ValueError("boom")
    event = JobExecutionEvent(
        code=EVENT_JOB_ERROR,
        job_id="run_scheduled_rag_backfill",
        jobstore="default",
        scheduled_run_time=None,
        exception=boom,
    )
    with caplog.at_level("ERROR", logger="haruhan"):
        _log_missed_or_failed_job(event)

    matching = [
        record
        for record in caplog.records
        if record.levelname == "ERROR" and "run_scheduled_rag_backfill" in record.message
    ]
    assert len(matching) == 1
    assert matching[0].exc_info is not None
    assert matching[0].exc_info[1] is boom


def test_scheduled_jobs_never_skip_due_to_misfire():
    """AsyncIOScheduler는 FastAPI/uvicorn과 같은 이벤트 루프를 공유하는데,
    APScheduler의 기본 misfire_grace_time(1초)은 예정된 실행 시각에 이벤트
    루프가 요청 처리 등으로 1초만 밀려도 그날 실행을 통째로 건너뛰게 만든다 -
    keep_supabase_alive처럼 "7일 연속 놓치면 Supabase가 자동 정지된다"는 걸
    막으려고 만든 job이 정작 이 좁은 기본값 때문에 놓치기 쉬운 상태였다.
    네 job 모두 misfire_grace_time=None(무제한)으로 등록되는지 확인한다."""
    from app.core.scheduler import scheduler, setup_scheduler_jobs

    for job in list(scheduler.get_jobs()):
        scheduler.remove_job(job.id)
    setup_scheduler_jobs()

    jobs = scheduler.get_jobs()
    assert len(jobs) == 4
    for job in jobs:
        assert job.misfire_grace_time is None, f"{job.id}의 misfire_grace_time이 무제한이 아님"

    for job in list(scheduler.get_jobs()):
        scheduler.remove_job(job.id)
