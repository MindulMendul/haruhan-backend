def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_guest_issues_tokens(client):
    response = client.post("/api/v1/auth/guest")
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"access_token", "refresh_token", "token_type"}


def test_guest_can_access_protected_endpoint(client):
    guest = client.post("/api/v1/auth/guest").json()

    me = client.get("/api/v1/users/me", headers=_auth_headers(guest["access_token"]))
    assert me.status_code == 200
    body = me.json()
    assert body["email"] is None
    assert body["is_guest"] is True


def test_two_guests_have_separate_data(client):
    guest_a = client.post("/api/v1/auth/guest").json()
    guest_b = client.post("/api/v1/auth/guest").json()

    client.post(
        "/api/v1/study/sessions",
        json={"title": "A의 학습"},
        headers=_auth_headers(guest_a["access_token"]),
    )

    listing_a = client.get("/api/v1/study/sessions", headers=_auth_headers(guest_a["access_token"]))
    listing_b = client.get("/api/v1/study/sessions", headers=_auth_headers(guest_b["access_token"]))

    assert len(listing_a.json()) == 1
    assert len(listing_b.json()) == 0


def test_guest_refresh_and_logout_work_normally(client):
    guest = client.post("/api/v1/auth/guest").json()

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": guest["refresh_token"]})
    assert refresh.status_code == 200
    new_tokens = refresh.json()

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert logout.status_code == 204

    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert reuse.status_code == 401


def test_guest_cannot_change_credentials_without_existing_password(client):
    guest = client.post("/api/v1/auth/guest").json()

    response = client.patch(
        "/api/v1/users/me",
        json={"email": "claim@example.com", "current_password": "anything"},
        headers=_auth_headers(guest["access_token"]),
    )
    assert response.status_code == 401
