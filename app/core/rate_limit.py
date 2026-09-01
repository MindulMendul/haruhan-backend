import logging
import time

from limits import parse
from redis.exceptions import RedisError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

logger = logging.getLogger("haruhan")

# redis-py의 socket_timeout/socket_connect_timeout 기본값(5초)보다 훨씬 넉넉하지만
# 무한정은 아닌 상한 - 아래 Limiter 생성자 주석 참고. 테스트에서도 그대로 참조해
# 실제로 적용되는 값과 어긋나지 않게 한다.
REDIS_SOCKET_TIMEOUT_SECONDS = 1

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
    # limits 라이브러리의 RedisStorage는 동기 redis-py 클라이언트를 그대로 쓰고,
    # slowapi는 그 hit() 호출을 @limiter.limit() 데코레이터 안에서 await 없이
    # 동기로 실행한다 - 이 앱은 uvicorn을 워커 1개로 띄우므로, 그 호출이 이벤트
    # 루프를 그대로 막는다. redis-py의 socket_timeout/socket_connect_timeout
    # 기본값은 5초라 Redis가 완전히 죽은 게 아니라 응답만 느려지는 상황(패킷
    # 유실 등, ConnectionError로 즉시 잡히는 완전 장애와는 다름)에서는 요청
    # 하나당 최대 5초씩 프로세스 전체가 멈출 수 있다 - 다른 안전장치들과 같은
    # "정상 사용량보다 훨씬 넉넉하지만 무한정은 아닌" 상한 철학(95/99/118/131
    # 라운드)으로, 로컬 Redis 왕복(보통 1ms 미만)보다 압도적으로 넉넉하면서도
    # 최악의 경우 이벤트 루프 정지 시간을 5초에서 1초로 줄인다.
    # slowapi의 storage_options 타입 힌트는 Dict[str, str]이지만, 실제로는 그대로
    # storage 생성자(RedisStorage -> redis.from_url)에 **kwargs로 전달될 뿐이라
    # socket_timeout처럼 int/float를 받는 옵션도 런타임에는 문제없이 동작한다 -
    # 실제로 Limiter를 만들어 redis 커넥션 풀에 정수 그대로 전달되는 것까지
    # tests/test_rate_limit_redis.py에서 확인했다.
    storage_options={
        "socket_connect_timeout": REDIS_SOCKET_TIMEOUT_SECONDS,  # type: ignore[dict-item]
        "socket_timeout": REDIS_SOCKET_TIMEOUT_SECONDS,  # type: ignore[dict-item]
    },
)


def check_rate_limit(key: str, rate_limit: str) -> tuple[bool, int]:
    """WebSocket처럼 @limiter.limit() 데코레이터를 못 쓰는 경로(HTTP 요청/응답 사이클
    바깥)에서 수동으로 레이트리밋을 확인한다. limiter와 같은 storage(메모리 또는
    REDIS_URL 설정 시 Redis)를 공유하므로 다중 워커 환경에서도 정확하다.

    (허용 여부, 거부됐을 때 재시도까지 남은 초) 튜플을 반환한다. 허용된 호출은 즉시
    카운트를 소비한다(test-then-hit이 아니라 hit 자체가 원자적).

    이 경로는 `limiter.limiter`(내부 저장소 전략 객체)를 직접 호출하는데, slowapi의
    `in_memory_fallback_enabled` 자동 전환은 그 프로퍼티가 `_storage_dead`일 때만
    폴백을 돌려주는 방식으로 동작하고, 그 플래그는 slowapi 내부적으로
    `@limiter.limit()` 데코레이터 경로(`_check_request_limit`)에서만 세팅된다 -
    이 함수는 그 경로를 거치지 않으므로 예전엔 Redis가 죽어도 이 플래그를 절대
    세우지 못하고 그냥 "허용"만 무한정 반복했다(우연히 같은 시점에 다른 HTTP
    요청이 이 플래그를 건드려주지 않는 한). 그 결과 REST 엔드포인트들은 Redis
    장애 중에도 (다소 부정확하지만) 인메모리 카운터로 계속 제한되는데, 정작
    가장 호출 비용이 큰 학습챗/면접복기 WebSocket 스트리밍만 장애 기간 내내
    완전 무제한이 되는 비일관성이 있었다. slowapi가 스스로 하는 것과 똑같이
    여기서도 직접 `_storage_dead`를 세워 인메모리 폴백을 실제로 작동시킨다 -
    이제 Redis가 죽어도 완전 무제한이 아니라 (여러 워커 간 정확도는 떨어지지만)
    이 프로세스의 인메모리 카운터로 제한이 계속된다. 폴백 자체도 실패하는
    경우에만(사실상 있을 수 없지만 방어적으로) "허용"으로 안전하게 처리한다 -
    레이트리밋 자체보다 서비스 가용성이 우선이라는 원래 원칙은 그대로 유지된다.
    """
    item = parse(rate_limit)
    try:
        if limiter.limiter.hit(item, key):
            return True, 0
        stats = limiter.limiter.get_window_stats(item, key)
        return False, max(0, round(stats.reset_time - time.time()))
    except RedisError:
        logger.exception("레이트리밋 저장소(Redis) 장애 감지 - 인메모리 폴백으로 전환합니다.")
        limiter._storage_dead = True
        try:
            if limiter.limiter.hit(item, key):
                return True, 0
            stats = limiter.limiter.get_window_stats(item, key)
            return False, max(0, round(stats.reset_time - time.time()))
        except RedisError:
            return True, 0
