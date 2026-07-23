import asyncio
from datetime import timedelta

from sqlalchemy import select

from app.core.clock import utcnow_naive
from app.core.tokens import hash_refresh_token
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User


def test_signup_login_refresh_logout_flow(client):
    signup = client.post(
        "/api/v1/auth/signup", json={"email": "flow@example.com", "password": "supersecret"}
    )
    assert signup.status_code == 201
    tokens = signup.json()
    assert set(tokens) == {"access_token", "refresh_token", "token_type"}

    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "flow@example.com"

    no_auth = client.get("/api/v1/users/me")
    assert no_auth.status_code == 401

    login = client.post(
        "/api/v1/auth/login", json={"email": "flow@example.com", "password": "supersecret"}
    )
    assert login.status_code == 200

    wrong_password = client.post(
        "/api/v1/auth/login", json={"email": "flow@example.com", "password": "wrongpass"}
    )
    assert wrong_password.status_code == 401

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 200
    new_tokens = refresh.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # 로테이션: 이미 사용한 refresh token은 재사용할 수 없다.
    reuse_old_refresh = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reuse_old_refresh.status_code == 401

    logout = client.post("/api/v1/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert logout.status_code == 204

    refresh_after_logout = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert refresh_after_logout.status_code == 401


def test_signup_duplicate_email_conflict(client):
    payload = {"email": "dup@example.com", "password": "supersecret"}
    first = client.post("/api/v1/auth/signup", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/auth/signup", json=payload)
    assert second.status_code == 409


def test_signup_rejects_short_password(client):
    response = client.post(
        "/api/v1/auth/signup", json={"email": "short@example.com", "password": "123"}
    )
    assert response.status_code == 422


def test_me_rejects_invalid_token(client):
    response = client.get(
        "/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_refresh_rejects_expired_token(client, db_session_factory):
    signup = client.post(
        "/api/v1/auth/signup", json={"email": "expired@example.com", "password": "supersecret"}
    )
    assert signup.status_code == 201

    raw_expired_token = "manually-inserted-expired-token"

    async def _insert_expired_token() -> None:
        async with db_session_factory() as session:
            user = (
                await session.execute(select(User).where(User.email == "expired@example.com"))
            ).scalar_one()
            session.add(
                RefreshToken(
                    user_id=user.id,
                    token_hash=hash_refresh_token(raw_expired_token),
                    expires_at=utcnow_naive() - timedelta(days=1),
                )
            )
            await session.commit()

    asyncio.run(_insert_expired_token())

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": raw_expired_token})
    assert response.status_code == 401
