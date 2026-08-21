from prometheus_client import REGISTRY

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
