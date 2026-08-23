import logging
import time

from limits import parse
from redis.exceptions import RedisError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

logger = logging.getLogger("haruhan")

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
    # Redis가 일시적으로 응답 못 하면(재시작/네트워크 문제 등) slowapi는 기본적으로
    # 그 예외를 그대로 올려보낸다 - 이 앱은 auth/chat/quiz 등 거의 모든 쓰기
    # 엔드포인트에 @limiter.limit()이 걸려 있어서, Redis 하나가 잠깐 흔들리면
    # 레이트리밋이 아니라 API 전체가 500으로 죽는 셈이 된다(직접 REDIS_URL을
    # 닫힌 포트로 돌려 재현 확인: redis.exceptions.ConnectionError가 그대로
    # 전역 예외 핸들러까지 올라감). in_memory_fallback_enabled=True로 켜두면
    # slowapi가 저장소 장애를 감지한 시점부터 자동으로 프로세스 내 메모리
    # 카운터로 전환해 요청은 계속 처리하고(여러 워커 간 정확도는 떨어지지만
    # 완전히 무방비인 것보다 낫다), 백그라운드에서 Redis가 살아나면 자동으로
    # 다시 Redis 기반으로 복귀한다.
    in_memory_fallback_enabled=True,
)


def check_rate_limit(key: str, rate_limit: str) -> tuple[bool, int]:
    """WebSocket처럼 @limiter.limit() 데코레이터를 못 쓰는 경로(HTTP 요청/응답 사이클
    바깥)에서 수동으로 레이트리밋을 확인한다. limiter와 같은 storage(메모리 또는
    REDIS_URL 설정 시 Redis)를 공유하므로 다중 워커 환경에서도 정확하다.

    (허용 여부, 거부됐을 때 재시도까지 남은 초) 튜플을 반환한다. 허용된 호출은 즉시
    카운트를 소비한다(test-then-hit이 아니라 hit 자체가 원자적).

    이 경로는 위 `limiter`의 `in_memory_fallback_enabled` 자동 복구 로직을 안 거치고
    `limiter.limiter`(내부 저장소 전략 객체)를 직접 호출한다 - Redis 장애 시
    WebSocket 메시지 하나 처리하자고 연결 전체가 처리되지 않은 예외로 끊기는 것을
    막기 위해, 여기서는 직접 예외를 잡아 "허용"으로 안전하게 처리한다(레이트리밋
    자체보다 서비스 가용성이 우선).
    """
    item = parse(rate_limit)
    try:
        if limiter.limiter.hit(item, key):
            return True, 0
        stats = limiter.limiter.get_window_stats(item, key)
        return False, max(0, round(stats.reset_time - time.time()))
    except RedisError:
        logger.exception("레이트리밋 저장소(Redis) 장애로 이번 확인은 통과 처리합니다.")
        return True, 0
