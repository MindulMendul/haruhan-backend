import pytest
from prometheus_client import REGISTRY

from app.core.config import get_settings
from app.core.dependencies import get_ollama_service


def _signup_and_get_token(client, email="metrics@example.com"):
    response = client.post("/api/v1/auth/signup", json={"email": email, "password": "supersecret"})
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_metrics_endpoint_exposes_prometheus_text_format(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "haruhan_http_requests_total" in response.text
    assert "haruhan_http_request_duration_seconds" in response.text


def test_metrics_endpoint_does_not_require_auth(client):
    response = client.get("/metrics")
    assert response.status_code == 200


def test_http_requests_total_uses_route_template_not_raw_path(client):
    token = _signup_and_get_token(client)

    quiz_a = client.post(
        "/api/v1/study/sessions", json={"title": "세션A"}, headers=_auth_headers(token)
    ).json()
    quiz_b = client.post(
        "/api/v1/study/sessions", json={"title": "세션B"}, headers=_auth_headers(token)
    ).json()

    # route.path는 자기 라우터의 prefix까지만 담고("/study/sessions/{session_id}"),
    # 그 위에서 include_router로 얹힌 v1_router의 "/api/v1" prefix는 포함하지 않는다.
    labels = {"method": "GET", "path": "/study/sessions/{session_id}", "status": "200"}
    before = REGISTRY.get_sample_value("haruhan_http_requests_total", labels) or 0.0

    client.get(f"/api/v1/study/sessions/{quiz_a['id']}", headers=_auth_headers(token))
    client.get(f"/api/v1/study/sessions/{quiz_b['id']}", headers=_auth_headers(token))

    after = REGISTRY.get_sample_value("haruhan_http_requests_total", labels)
    assert after == before + 2


def test_metrics_endpoint_is_labeled_as_unmatched_route(client):
    labels = {"method": "GET", "path": "unmatched", "status": "404"}
    before = REGISTRY.get_sample_value("haruhan_http_requests_total", labels) or 0.0

    client.get("/this-route-does-not-exist")

    after = REGISTRY.get_sample_value("haruhan_http_requests_total", labels)
    assert after == before + 1


def test_user_signup_increments_signup_counter(client):
    before = REGISTRY.get_sample_value("haruhan_user_signups_total") or 0.0
    _signup_and_get_token(client, email="signup-metric@example.com")
    after = REGISTRY.get_sample_value("haruhan_user_signups_total")
    assert after == before + 1


def test_guest_upgrade_increments_guest_conversion_counter(client):
    before = REGISTRY.get_sample_value("haruhan_guest_conversions_total") or 0.0

    guest = client.post("/api/v1/auth/guest")
    assert guest.status_code == 201
    token = guest.json()["access_token"]

    upgrade = client.post(
        "/api/v1/users/me/upgrade",
        json={"email": "guest-metric@example.com", "password": "supersecret"},
        headers=_auth_headers(token),
    )
    assert upgrade.status_code == 200

    after = REGISTRY.get_sample_value("haruhan_guest_conversions_total")
    assert after == before + 1


class FakeOllamaService:
    async def generate_json(self, prompt, model, schema):
        import json

        return json.dumps(
            {
                "questions": [
                    {
                        "question": "질문?",
                        "choices": ["A", "B"],
                        "correct_answer": "A",
                        "explanation": "설명",
                    }
                ]
            }
        )

    async def embed(self, text, model):
        return [1.0, 0.0, 0.0]


def test_quiz_creation_increments_quiz_created_counter(client):
    client.app.dependency_overrides[get_ollama_service] = lambda: FakeOllamaService()
    token = _signup_and_get_token(client, email="quiz-metric@example.com")

    before = REGISTRY.get_sample_value("haruhan_quiz_created_total") or 0.0
    response = client.post(
        "/api/v1/quizzes",
        json={"title": "메트릭 퀴즈", "source_text": "학습 내용"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    after = REGISTRY.get_sample_value("haruhan_quiz_created_total")
    assert after == before + 1


def test_ws_connection_increments_and_decrements_active_gauge(client):
    """MetricsMiddleware(core/metrics.py)는 ASGI "http" scope만 다뤄서
    WebSocket 연결은 지금까지 haruhan_http_requests_total 등 어떤 지표에도
    잡히지 않았다 - 99/123/140/164/176라운드가 공들여 만든 동시 연결 상한
    (DB 커넥션 풀 고갈 방지 안전장치)이 실제로 얼마나 여유가 있는지 운영자가
    Grafana에서 전혀 볼 수 없었다. 연결이 열려 있는 동안 게이지가 늘고,
    닫히면 다시 줄어드는지 확인한다."""
    token = _signup_and_get_token(client, email="ws-gauge@example.com")
    create = client.post(
        "/api/v1/study/sessions", json={"title": "게이지 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    before = REGISTRY.get_sample_value("haruhan_ws_active_connections") or 0.0

    with client.websocket_connect(f"/api/v1/study/sessions/{session_id}/stream?token={token}"):
        during = REGISTRY.get_sample_value("haruhan_ws_active_connections")
        assert during == before + 1

    after = REGISTRY.get_sample_value("haruhan_ws_active_connections")
    assert after == before


def test_ws_connection_rejected_at_limit_increments_rejected_counter(client, monkeypatch):
    """limit_ws_connections(core/dependencies.py)가 상한 초과로 연결을 거부할
    때마다 이 카운터가 늘어나는지 확인한다 - 학습챗/면접복기 두 라우트가
    공유하는 단일 카운터/단일 상한이라 라벨 없이 하나로 합산된다."""
    from starlette.testclient import WebSocketDisconnect

    monkeypatch.setenv("MAX_CONCURRENT_WS_CONNECTIONS", "1")
    get_settings.cache_clear()
    token = _signup_and_get_token(client, email="ws-rejected@example.com")
    create = client.post(
        "/api/v1/study/sessions", json={"title": "거부 카운터 테스트"}, headers=_auth_headers(token)
    )
    session_id = create.json()["id"]

    before = REGISTRY.get_sample_value("haruhan_ws_connections_rejected_total") or 0.0

    with client.websocket_connect(f"/api/v1/study/sessions/{session_id}/stream?token={token}"):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                f"/api/v1/study/sessions/{session_id}/stream?token={token}"
            ) as second_ws:
                second_ws.receive_json()

    after = REGISTRY.get_sample_value("haruhan_ws_connections_rejected_total")
    assert after == before + 1
