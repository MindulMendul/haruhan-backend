from slowapi import Limiter
from slowapi.util import get_remote_address

# 앱 전체에서 공유하는 단일 Limiter 인스턴스.
# 라우트에서는 @limiter.limit(...) 데코레이터로 사용하고,
# main.py에서 app.state.limiter로 등록해 예외 핸들러와 연결한다.
limiter = Limiter(key_func=get_remote_address)
