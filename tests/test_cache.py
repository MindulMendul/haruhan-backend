from app.core.cache import TTLCache


def test_ttl_cache_returns_none_when_empty():
    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    assert cache.get() is None


def test_ttl_cache_returns_value_within_ttl(monkeypatch):
    import app.core.cache as cache_module

    fake_time = [100.0]
    monkeypatch.setattr(cache_module.time, "monotonic", lambda: fake_time[0])

    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    cache.set("value")

    fake_time[0] += 59
    assert cache.get() == "value"


def test_ttl_cache_expires_after_ttl(monkeypatch):
    import app.core.cache as cache_module

    fake_time = [100.0]
    monkeypatch.setattr(cache_module.time, "monotonic", lambda: fake_time[0])

    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    cache.set("value")

    fake_time[0] += 61
    assert cache.get() is None


def test_ttl_cache_clear_removes_cached_value():
    cache: TTLCache[str] = TTLCache(ttl_seconds=60)
    cache.set("value")
    cache.clear()
    assert cache.get() is None
