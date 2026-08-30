import asyncio


def test_liveness_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "haruhan-backend"


def test_readiness_without_db_configured(client):
    # 테스트 환경에는 DATABASE_URL이 없으므로 readiness는 503이어야 한다.
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


class FakeOllamaService:
    async def list_models(self):
        return [{"name": "qwen2.5:3b"}]


class FailingOllamaService:
    async def list_models(self):
        from app.services.ollama_service import OllamaServiceError

        raise OllamaServiceError("boom")


def test_readiness_when_all_dependencies_healthy(client, monkeypatch):
    import app.api.v1.routes.health as health_module
    from app.core.dependencies import get_ollama_service

    async def _fake_check_db_health(timeout_seconds):
        return True

    monkeypatch.setattr(health_module, "check_db_health", _fake_check_db_health)
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()

    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert body["redis"] == "not_configured"
    assert body["ollama"] == "connected"


def test_readiness_when_ollama_unreachable(client, monkeypatch):
    import app.api.v1.routes.health as health_module
    from app.core.dependencies import get_ollama_service

    async def _fake_check_db_health(timeout_seconds):
        return True

    monkeypatch.setattr(health_module, "check_db_health", _fake_check_db_health)
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()

    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["ollama"] == "disconnected"


def test_readiness_caches_result_within_ttl(client, monkeypatch):
    """/health/ready는 인증이 없다(트래픽 라우팅 판단용이라 로그인 절차를 둘 수
    없음) - 그런데 호출할 때마다 Ollama에 실제 요청을 보낸다. 캐시가 없으면
    익명 호출자가 원하는 만큼 반복 호출해서 상류 서비스(Ollama)에 부하를 줄 수
    있었다(121라운드가 /models에서 고친 것과 같은 모양의 문제) - 짧은 TTL
    캐시로, 호출 빈도와 무관하게 실제 Ollama 호출이 캐시 주기당 한 번만
    일어나는지 확인한다."""
    import app.api.v1.routes.health as health_module
    from app.core.dependencies import get_ollama_service

    async def _fake_check_db_health(timeout_seconds):
        return True

    monkeypatch.setattr(health_module, "check_db_health", _fake_check_db_health)

    class CountingOllamaService:
        def __init__(self):
            self.call_count = 0

        async def list_models(self):
            self.call_count += 1
            return [{"name": "qwen2.5:3b"}]

    fake = CountingOllamaService()
    client.app.dependency_overrides[get_ollama_service] = lambda: fake

    first = client.get("/health/ready")
    second = client.get("/health/ready")

    assert fake.call_count == 1
    assert first.json() == second.json()
    assert first.status_code == 200


def test_readiness_reports_redis_disconnected_when_configured_but_unreachable(
    client, monkeypatch
):
    import app.api.v1.routes.health as health_module
    from app.core.dependencies import get_ollama_service

    async def _fake_check_db_health(timeout_seconds):
        return True

    async def _fake_check_redis_health(redis_url, timeout_seconds):
        return False

    monkeypatch.setattr(health_module, "check_db_health", _fake_check_db_health)
    monkeypatch.setattr(health_module, "check_redis_health", _fake_check_redis_health)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    from app.core.config import get_settings

    get_settings.cache_clear()
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()

    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["redis"] == "disconnected"


def test_get_or_check_readiness_coalesces_concurrent_cache_misses(monkeypatch):
    """캐시가 막 만료된 순간 동시에 들어온 요청들은 락 없이는 각자 독립적으로
    Ollama를 호출한다(models.py의 같은 이름 테스트와 같은 이유) - 여러 호출자가
    캐시가 비어있는 상태에서 동시에 진입해도 실제 Ollama 호출은 정확히 한 번만
    일어나고, 나머지는 그 결과를 그대로 받아가는지 확인한다."""
    import app.api.v1.routes.health as health_module
    from app.api.v1.routes.health import _get_or_check_readiness, _readiness_cache
    from app.core.config import get_settings

    async def _fake_check_db_health(timeout_seconds):
        return True

    monkeypatch.setattr(health_module, "check_db_health", _fake_check_db_health)

    class SlowCountingOllamaService:
        def __init__(self):
            self.call_count = 0

        async def list_models(self):
            self.call_count += 1
            # 캐시 미스 상태에서 여러 호출이 겹칠 시간을 벌어준다 - 이 sleep
            # 동안 락 없이 진입한 다른 호출들이 각자 이 메서드를 또 부르는지가
            # 이 테스트가 확인하려는 지점이다.
            await asyncio.sleep(0.05)
            return [{"name": "qwen2.5:3b"}]

    fake = SlowCountingOllamaService()
    _readiness_cache.clear()
    settings = get_settings()

    async def _run():
        return await asyncio.gather(
            *[_get_or_check_readiness(settings, fake) for _ in range(5)]
        )

    results = asyncio.run(_run())

    assert fake.call_count == 1
    assert all(r == results[0] for r in results)
    assert results[0][0] == 200


def test_get_or_check_readiness_runs_db_redis_ollama_checks_concurrently(monkeypatch):
    """DB/Redis/Ollama 확인을 순서대로(직렬로) await하면, 각 확인이
    health_check_timeout_seconds(166라운드) 안에 끝나더라도 셋이 동시에
    느려지는 실제 장애 상황에서는 전체 응답 시간이 그 합(최대 3배)까지
    늘어난다 - readiness probe는 오히려 이런 상황에서 가장 빠르게 답해야
    트래픽 라우팅 판단에 의미가 있고, 오케스트레이터 자체의 probe
    타임아웃이 이 앱의 판단보다 먼저 끊어버릴 위험도 있다. asyncio.gather로
    동시에 실행해 전체 대기 시간이 가장 느린 확인 하나만큼으로 끝나는지
    확인한다(순서대로 실행하면 이 테스트가 정확히 실패하는 것도 확인함)."""
    import app.api.v1.routes.health as health_module
    from app.api.v1.routes.health import _get_or_check_readiness, _readiness_cache
    from app.core.config import get_settings

    _DELAY_SECONDS = 0.2

    async def _fake_check_db_health(timeout_seconds):
        await asyncio.sleep(_DELAY_SECONDS)
        return True

    async def _fake_check_redis_health(redis_url, timeout_seconds):
        await asyncio.sleep(_DELAY_SECONDS)
        return True

    monkeypatch.setattr(health_module, "check_db_health", _fake_check_db_health)
    monkeypatch.setattr(health_module, "check_redis_health", _fake_check_redis_health)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    get_settings.cache_clear()
    settings = get_settings()

    class SlowOllamaService:
        async def list_models(self):
            await asyncio.sleep(_DELAY_SECONDS)
            return [{"name": "qwen2.5:3b"}]

    _readiness_cache.clear()

    async def _run():
        loop = asyncio.get_running_loop()
        start = loop.time()
        result = await _get_or_check_readiness(settings, SlowOllamaService())
        elapsed = loop.time() - start
        return result, elapsed

    result, elapsed = asyncio.run(_run())

    assert result[0] == 200
    # 세 확인이 순서대로였다면 최소 3 * _DELAY_SECONDS(0.6초)가 걸린다 -
    # 동시 실행이라면 가장 느린 확인 하나(0.2초)에 가까운 시간만 걸려야 한다.
    assert elapsed < _DELAY_SECONDS * 2
