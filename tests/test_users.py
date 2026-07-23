def _signup_and_get_tokens(client, email="user@example.com", password="supersecret"):
    response = client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    assert response.status_code == 201
    return response.json()


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_update_email_requires_current_password(client):
    tokens = _signup_and_get_tokens(client)
    response = client.patch(
        "/api/v1/users/me",
        json={"email": "new@example.com"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 422


def test_update_email_wrong_current_password(client):
    tokens = _signup_and_get_tokens(client)
    response = client.patch(
        "/api/v1/users/me",
        json={"email": "new@example.com", "current_password": "wrongpass"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 401


def test_update_email_success(client):
    tokens = _signup_and_get_tokens(client)
    response = client.patch(
        "/api/v1/users/me",
        json={"email": "new@example.com", "current_password": "supersecret"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200
    assert response.json()["email"] == "new@example.com"

    me = client.get("/api/v1/users/me", headers=_auth_headers(tokens["access_token"]))
    assert me.json()["email"] == "new@example.com"


def test_update_email_conflict_with_existing_user(client):
    _signup_and_get_tokens(client, email="taken@example.com")
    tokens_b = _signup_and_get_tokens(client, email="b@example.com")

    response = client.patch(
        "/api/v1/users/me",
        json={"email": "taken@example.com", "current_password": "supersecret"},
        headers=_auth_headers(tokens_b["access_token"]),
    )
    assert response.status_code == 409


def test_update_password_success_and_old_password_stops_working(client):
    tokens = _signup_and_get_tokens(client, email="pw@example.com")
    response = client.patch(
        "/api/v1/users/me",
        json={"password": "newsupersecret", "current_password": "supersecret"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 200

    old_login = client.post(
        "/api/v1/auth/login", json={"email": "pw@example.com", "password": "supersecret"}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login", json={"email": "pw@example.com", "password": "newsupersecret"}
    )
    assert new_login.status_code == 200


def test_update_without_any_field_requires_no_current_password(client):
    tokens = _signup_and_get_tokens(client)
    response = client.patch(
        "/api/v1/users/me", json={}, headers=_auth_headers(tokens["access_token"])
    )
    assert response.status_code == 200
