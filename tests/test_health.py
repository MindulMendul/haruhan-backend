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


def test_readiness_when_db_healthy(client, monkeypatch):
    import app.api.v1.routes.health as health_module

    async def _fake_check_db_health():
        return True

    monkeypatch.setattr(health_module, "check_db_health", _fake_check_db_health)

    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
