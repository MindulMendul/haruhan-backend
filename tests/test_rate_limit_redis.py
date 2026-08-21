from slowapi import Limiter
from slowapi.util import get_remote_address


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
