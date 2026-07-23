from datetime import datetime, timezone


def utcnow_naive() -> datetime:
    """DB에는 tz 정보 없이 UTC 기준 naive datetime으로 통일해서 저장/비교한다.

    SQLite(테스트)와 Postgres(운영)에서 tz-aware datetime 처리 방식이 달라
    naive/aware를 섞어 비교하면 예외나 오동작이 날 수 있어, 앱 전체에서
    항상 UTC naive로 통일한다.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
