import time
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """아주 단순한 단일 값 TTL 캐시.

    프로세스 메모리에만 있어서 워커가 여러 개면 워커마다 따로 캐시하지만, 모델
    목록처럼 자주 안 바뀌고 정합성이 크리티컬하지 않은 데이터에는 그 정도로
    충분하다 - 워커 수만큼 Ollama 호출이 늘어나는 정도지 데이터가 틀리게
    나오는 문제는 아니다.
    """

    def __init__(self, ttl_seconds: float) -> None:
        self._ttl_seconds = ttl_seconds
        self._value: T | None = None
        self._cached_at: float | None = None

    def get(self) -> T | None:
        if self._cached_at is None:
            return None
        if time.monotonic() - self._cached_at > self._ttl_seconds:
            return None
        return self._value

    def set(self, value: T) -> None:
        self._value = value
        self._cached_at = time.monotonic()

    def clear(self) -> None:
        self._value = None
        self._cached_at = None
