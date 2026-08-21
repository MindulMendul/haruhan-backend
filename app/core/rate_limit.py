import time

from limits import parse
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

# 앱 전체에서 공유하는 단일 Limiter 인스턴스.
# 라우트에서는 @limiter.limit(...) 데코레이터로 사용하고,
# main.py에서 app.state.limiter로 등록해 예외 핸들러와 연결한다.
#
# REDIS_URL이 설정되면 여러 워커/인스턴스가 카운터를 공유하는 Redis 스토리지를 쓴다.
# 비어있으면 인메모리 스토리지로 동작하며, 이는 단일 프로세스에서만 정확하다.
_settings = get_settings()
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_settings.redis_url or "memory://",
    # 클라이언트가 몇 초 후에 재시도하면 되는지 알 수 있도록 Retry-After 등
    # 레이트리밋 관련 헤더를 응답에 싣는다 (기본값 False라 명시적으로 켜야 함).
    headers_enabled=True,
)


def check_rate_limit(key: str, rate_limit: str) -> tuple[bool, int]:
    """WebSocket처럼 @limiter.limit() 데코레이터를 못 쓰는 경로(HTTP 요청/응답 사이클
    바깥)에서 수동으로 레이트리밋을 확인한다. limiter와 같은 storage(메모리 또는
    REDIS_URL 설정 시 Redis)를 공유하므로 다중 워커 환경에서도 정확하다.

    (허용 여부, 거부됐을 때 재시도까지 남은 초) 튜플을 반환한다. 허용된 호출은 즉시
    카운트를 소비한다(test-then-hit이 아니라 hit 자체가 원자적).
    """
    item = parse(rate_limit)
    if limiter.limiter.hit(item, key):
        return True, 0
    stats = limiter.limiter.get_window_stats(item, key)
    return False, max(0, round(stats.reset_time - time.time()))
