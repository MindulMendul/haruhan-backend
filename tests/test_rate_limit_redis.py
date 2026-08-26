from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from limits import parse
from redis.exceptions import RedisError
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core import rate_limit as rate_limit_module


def test_limiter_uses_redis_storage_when_redis_url_configured():
    """app.core.rate_limit이 REDIS_URL 설정 시 실제로 Redis 백엔드로 전환되는지 확인한다.

    Redis 서버가 없어도 통과해야 한다 - limits 라이브러리는 스토리지 생성 시점에는
    연결하지 않고, 실제 요청이 들어와 체크할 때만 연결을 시도한다 (지연 연결).
    """
    limiter = Limiter(key_func=get_remote_address, storage_uri="redis://localhost:6399/0")
    assert type(limiter._storage).__name__ == "RedisStorage"


def test_limiter_uses_memory_storage_when_no_redis_url():
    limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")
    assert type(limiter._storage).__name__ == "MemoryStorage"


def test_redis_storage_has_bounded_socket_timeouts():
    """limits의 RedisStorage는 동기 redis-py 클라이언트를 그대로 쓰고, slowapi는
    @limiter.limit() 안에서 그 hit() 호출을 await 없이 동기로 실행한다 - uvicorn을
    워커 1개로 띄우는 이 앱에서는 그 호출이 이벤트 루프를 그대로 막는다.
    socket_timeout/socket_connect_timeout을 명시하지 않으면 redis-py 기본값(5초)이
    그대로 적용돼, Redis가 완전히 죽은 게 아니라 응답만 느려지는 상황(패킷 유실
    등)에서 요청 하나당 최대 5초씩 프로세스 전체가 멈출 수 있다. app.core.rate_limit
    이 실제로 생성하는 것과 같은 storage_options로 Limiter를 만들어, 내부 redis
    커넥션 풀에 그 값이 전달되는지 확인한다(서버에 연결하지는 않음 - limits는
    스토리지 생성 시점에는 연결하지 않고 지연 연결한다)."""
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri="redis://localhost:6399/0",
        storage_options={
            "socket_connect_timeout": rate_limit_module.REDIS_SOCKET_TIMEOUT_SECONDS,
            "socket_timeout": rate_limit_module.REDIS_SOCKET_TIMEOUT_SECONDS,
        },
    )
    connection_kwargs = limiter._storage.storage.connection_pool.connection_kwargs
    assert connection_kwargs["socket_timeout"] == rate_limit_module.REDIS_SOCKET_TIMEOUT_SECONDS
    assert connection_kwargs["socket_connect_timeout"] == rate_limit_module.REDIS_SOCKET_TIMEOUT_SECONDS


def test_app_rate_limiter_has_bounded_socket_timeouts_configured():
    """app.core.rate_limit.limiter(실제로 앱 전체가 공유하는 인스턴스)가 위
    타임아웃 상한을 실제로 storage_options로 들고 있는지 확인한다 - 이 인스턴스는
    보통 memory:// 스토리지라 connection_pool이 없으므로, RedisStorage 생성 시점에
    전달되는 storage_options 자체를 확인한다."""
    assert rate_limit_module.limiter._storage_options == {
        "socket_connect_timeout": rate_limit_module.REDIS_SOCKET_TIMEOUT_SECONDS,
        "socket_timeout": rate_limit_module.REDIS_SOCKET_TIMEOUT_SECONDS,
    }


def test_limiter_falls_back_to_memory_when_redis_unreachable(caplog):
    """이 앱은 auth/chat/quiz 등 거의 모든 쓰기 엔드포인트에 @limiter.limit()이
    걸려 있다 - in_memory_fallback_enabled 없이는 Redis가 잠깐 끊겨도(재시작,
    네트워크 문제 등) 그 예외가 그대로 올라가 API 전체가 500으로 죽는다.
    실제 라우트를 하나 만들어 호출해서, Limiter가 저장소 장애를 감지하고
    인메모리로 자동 전환해 요청을 500 없이 계속 처리하는지 확인한다."""
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri="redis://127.0.0.1:1/0",
        in_memory_fallback_enabled=True,
    )

    app = FastAPI()
    app.state.limiter = limiter

    @app.get("/probe")
    @limiter.limit("5/minute")
    async def probe(request: Request) -> dict:
        return {"ok": True}

    with caplog.at_level("WARNING", logger="slowapi"), TestClient(app) as client:
        response = client.get("/probe")

    assert response.status_code == 200
    assert "falling back to in-memory storage" in caplog.text
    assert limiter._storage_dead is True


def test_check_rate_limit_allows_request_when_redis_unreachable(monkeypatch, caplog):
    """check_rate_limit()은 WebSocket 경로에서 limiter.limiter(내부 저장소 전략
    객체)를 직접 호출한다 - Redis 장애 시 이 경로도 예외를 그대로 올리지 않고
    "허용"으로 안전하게 처리하는지 확인한다(첫 호출은 아직 인메모리 폴백으로
    전환하기 전이라 무조건 허용됨 - 실제로 폴백이 카운트를 추적하기 시작하는지는
    아래 test_check_rate_limit_falls_back_to_in_memory_limiting_when_redis_dead가
    확인한다)."""
    limiter = Limiter(
        key_func=get_remote_address, storage_uri="redis://127.0.0.1:1/0", in_memory_fallback_enabled=True
    )
    monkeypatch.setattr(rate_limit_module, "limiter", limiter)

    with caplog.at_level("ERROR", logger="haruhan"):
        allowed, retry_after = rate_limit_module.check_rate_limit("test-key", "5/minute")

    assert allowed is True
    assert retry_after == 0
    assert "레이트리밋 저장소(Redis) 장애" in caplog.text


def test_check_rate_limit_falls_back_to_in_memory_limiting_when_redis_dead(monkeypatch):
    """예전엔 limiter.limiter를 직접 호출하는 이 경로가 slowapi의 `_storage_dead`
    플래그를 절대 세우지 못해(그 플래그는 @limiter.limit() 데코레이터 경로에서만
    세팅됨), Redis 장애 중엔 이 함수가 호출 횟수와 무관하게 계속 "허용"만
    반복했다 - 즉 REST 엔드포인트는 (다소 부정확해도) 인메모리 카운터로 계속
    제한되는데 WebSocket 경로만 장애 기간 내내 완전 무제한이 되는 비일관성이
    있었다. 이제 직접 `_storage_dead`를 세워 인메모리 폴백을 실제로 작동시키므로,
    Redis가 죽은 상태에서도 설정한 한도(2/minute)를 넘기면 세 번째 호출부터는
    거부돼야 한다 - test_manual_rate_limit.py의
    test_check_rate_limit_allows_up_to_limit_then_blocks와 같은 모양이지만
    Redis 장애 상황에서도 그 속성이 유지되는지가 다른 점이다."""
    limiter = Limiter(
        key_func=get_remote_address, storage_uri="redis://127.0.0.1:1/0", in_memory_fallback_enabled=True
    )
    monkeypatch.setattr(rate_limit_module, "limiter", limiter)

    allowed_1, _ = rate_limit_module.check_rate_limit("fallback-key", "2/minute")
    allowed_2, _ = rate_limit_module.check_rate_limit("fallback-key", "2/minute")
    allowed_3, retry_after_3 = rate_limit_module.check_rate_limit("fallback-key", "2/minute")

    assert (allowed_1, allowed_2, allowed_3) == (True, True, False)
    assert retry_after_3 >= 0
    assert limiter._storage_dead is True


def test_check_rate_limit_denies_immediately_when_fallback_already_at_limit(monkeypatch):
    """위 테스트는 첫 호출이 Redis 장애를 감지해 인메모리 폴백으로 전환한 뒤
    "허용"으로 응답하고, 그 다음다음 호출에서야(_storage_dead가 이미 True라
    바깥쪽 try에서 바로) 거부된다 - 그래서 안쪽 재시도 블록 자체의 거부 분기
    (limiter.limiter.hit()이 재시도 시점에 곧바로 False를 돌려주는 경우)는
    한 번도 실행되지 않는다. 폴백 리미터를 미리 한도까지 채워둔 뒤 Redis
    장애를 처음 감지하는 바로 그 순간부터 거부가 나오는지 확인해, 그 분기를
    직접 노린다."""
    limiter = Limiter(
        key_func=get_remote_address, storage_uri="redis://127.0.0.1:1/0", in_memory_fallback_enabled=True
    )
    monkeypatch.setattr(rate_limit_module, "limiter", limiter)

    item = parse("1/minute")
    assert limiter._fallback_limiter.hit(item, "already-full-key") is True

    allowed, retry_after = rate_limit_module.check_rate_limit("already-full-key", "1/minute")

    assert allowed is False
    assert retry_after >= 0
    assert limiter._storage_dead is True


def test_check_rate_limit_allows_when_fallback_itself_fails(monkeypatch):
    """인메모리 폴백 자체가 실패하는 건 사실상 있을 수 없지만(디스크 I/O나
    네트워크가 필요 없는 프로세스 내 메모리 구조라), 방어적으로 이 경우에도
    예외를 그대로 올리지 않고 레이트리밋 자체보다 서비스 가용성을 우선해
    "허용"으로 안전하게 처리하는지 확인한다."""
    limiter = Limiter(
        key_func=get_remote_address, storage_uri="redis://127.0.0.1:1/0", in_memory_fallback_enabled=True
    )
    monkeypatch.setattr(rate_limit_module, "limiter", limiter)

    def _always_fail(*args, **kwargs):
        raise RedisError("시뮬레이션된 폴백 실패")

    monkeypatch.setattr(limiter._fallback_limiter, "hit", _always_fail)

    allowed, retry_after = rate_limit_module.check_rate_limit("test-key", "5/minute")

    assert allowed is True
    assert retry_after == 0
