def _signup_and_get_token(client, email="export@example.com"):
    response = client.post("/api/v1/auth/signup", json={"email": email, "password": "supersecret"})
    assert response.status_code == 201
    return response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_export_my_data_requires_auth(client):
    response = client.get("/api/v1/export/me")
    assert response.status_code == 401


def test_export_my_data_returns_empty_lists_for_new_user(client):
    token = _signup_and_get_token(client)
    response = client.get("/api/v1/export/me", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["study_sessions"] == []
    assert body["quizzes"] == []
    assert body["interview_practice_sessions"] == []
    assert body["interview_reviews"] == []
    assert "exported_at" in body


def test_export_my_data_includes_created_study_session(client):
    token = _signup_and_get_token(client)
    create = client.post(
        "/api/v1/study/sessions", json={"title": "세션"}, headers=_auth_headers(token)
    )
    assert create.status_code == 201

    response = client.get("/api/v1/export/me", headers=_auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert len(body["study_sessions"]) == 1
    assert body["study_sessions"][0]["title"] == "세션"
