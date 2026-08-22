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


def test_update_password_rejects_password_over_byte_limit(client):
    # 스키마의 max_length=72는 "문자 수" 기준이라, 멀티바이트 문자로 72자를 채우면
    # 글자 수 검증(422)은 통과하지만 UTF-8로 인코딩하면 72바이트를 넘는다 -
    # 그 경우 hash_password()의 바이트 길이 가드가 400으로 잡아내야 한다.
    tokens = _signup_and_get_tokens(client, email="longpw@example.com")
    password = "가" * 72
    response = client.patch(
        "/api/v1/users/me",
        json={"password": password, "current_password": "supersecret"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 400


def test_upgrade_guest_success(client):
    guest = client.post("/api/v1/auth/guest")
    assert guest.status_code == 201
    token = guest.json()["access_token"]

    upgrade = client.post(
        "/api/v1/users/me/upgrade",
        json={"email": "upgraded@example.com", "password": "supersecret"},
        headers=_auth_headers(token),
    )
    assert upgrade.status_code == 200
    assert upgrade.json()["email"] == "upgraded@example.com"

    login = client.post(
        "/api/v1/auth/login", json={"email": "upgraded@example.com", "password": "supersecret"}
    )
    assert login.status_code == 200


def test_upgrade_guest_rejects_already_real_account(client):
    tokens = _signup_and_get_tokens(client, email="already-real@example.com")
    response = client.post(
        "/api/v1/users/me/upgrade",
        json={"email": "another@example.com", "password": "supersecret"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 409


def test_upgrade_guest_conflict_with_existing_email(client):
    _signup_and_get_tokens(client, email="taken-upgrade@example.com")
    guest = client.post("/api/v1/auth/guest")
    token = guest.json()["access_token"]

    response = client.post(
        "/api/v1/users/me/upgrade",
        json={"email": "taken-upgrade@example.com", "password": "supersecret"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 409


def test_upgrade_guest_rejects_password_over_byte_limit(client):
    guest = client.post("/api/v1/auth/guest")
    token = guest.json()["access_token"]
    password = "가" * 72

    response = client.post(
        "/api/v1/users/me/upgrade",
        json={"email": "upgrade-longpw@example.com", "password": password},
        headers=_auth_headers(token),
    )
    assert response.status_code == 400


def test_update_without_any_field_requires_no_current_password(client):
    tokens = _signup_and_get_tokens(client)
    response = client.patch(
        "/api/v1/users/me", json={}, headers=_auth_headers(tokens["access_token"])
    )
    assert response.status_code == 200


def test_delete_account_requires_current_password_for_real_account(client):
    tokens = _signup_and_get_tokens(client, email="delete-noconfirm@example.com")
    response = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 401


def test_delete_account_wrong_current_password(client):
    tokens = _signup_and_get_tokens(client, email="delete-wrongpw@example.com")
    response = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"current_password": "wrongpass"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 401


def test_delete_account_success_for_real_account(client):
    tokens = _signup_and_get_tokens(client, email="delete-ok@example.com")
    response = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"current_password": "supersecret"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 204

    me = client.get("/api/v1/users/me", headers=_auth_headers(tokens["access_token"]))
    assert me.status_code == 401

    # 이메일이 자유로워졌으니 같은 이메일로 다시 가입할 수 있어야 한다.
    resignup = client.post(
        "/api/v1/auth/signup", json={"email": "delete-ok@example.com", "password": "anotherpass"}
    )
    assert resignup.status_code == 201


def test_delete_guest_account_without_password(client):
    guest = client.post("/api/v1/auth/guest")
    assert guest.status_code == 201
    token = guest.json()["access_token"]

    response = client.request(
        "DELETE", "/api/v1/users/me", json={}, headers=_auth_headers(token)
    )
    assert response.status_code == 204

    me = client.get("/api/v1/users/me", headers=_auth_headers(token))
    assert me.status_code == 401
