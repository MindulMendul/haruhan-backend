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
)
