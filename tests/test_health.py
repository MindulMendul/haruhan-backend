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

    async def _fake_check_db_health():
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

    async def _fake_check_db_health():
        return True

    monkeypatch.setattr(health_module, "check_db_health", _fake_check_db_health)
    client.app.dependency_overrides[get_ollama_service] = lambda: FailingOllamaService()

    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["ollama"] == "disconnected"


def test_readiness_reports_redis_disconnected_when_configured_but_unreachable(
    client, monkeypatch
):
    import app.api.v1.routes.health as health_module
    from app.core.dependencies import get_ollama_service

    async def _fake_check_db_health():
        return True

    async def _fake_check_redis_health(redis_url):
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
