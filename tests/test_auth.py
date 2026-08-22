import asyncio
from datetime import timedelta

from sqlalchemy import select

from app.core.clock import utcnow_naive
from app.core.config import get_settings
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
    # 레이트리밋 헤더는 실패(429)뿐 아니라 성공 응답에도 항상 실려야 한다
    # (headers_enabled=True로 켠 뒤 라우트마다 response: Response를 안 받으면 500이 났던 회귀).
    assert "X-RateLimit-Limit" in signup.headers

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
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"

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


def test_refresh_rejects_unknown_token(client):
    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "never-issued-token"}
    )
    assert response.status_code == 401


def test_refresh_token_reuse_revokes_all_sessions(client):
    signup = client.post(
        "/api/v1/auth/signup", json={"email": "reuse@example.com", "password": "supersecret"}
    )
    assert signup.status_code == 201
    tokens = signup.json()

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 200
    new_tokens = refresh.json()

    # 탈취범이 이미 로테이션되어 폐기된 옛 토큰을 재사용 시도한다.
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401

    # 재사용 탐지로 정상 사용자가 갖고 있던, 아직 한 번도 안 쓴 최신 토큰까지
    # 강제로 끊겼어야 한다 (단순 로테이션이라면 이 토큰은 여전히 유효했을 것).
    still_using_latest = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert still_using_latest.status_code == 401


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
    assert response.json()["error"]["code"] == "invalid_token"


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


def test_signup_rejects_password_over_byte_limit_despite_passing_char_limit(client):
    # 스키마의 max_length=72는 "문자 수" 기준이라, 멀티바이트 문자로 72자를 채우면
    # 글자 수 검증(422)은 통과하지만 UTF-8로 인코딩하면 72바이트를 넘는다 -
    # 그 경우 hash_password()의 바이트 길이 가드가 400으로 잡아내야 한다.
    password = "가" * 72
    assert len(password) == 72
    assert len(password.encode("utf-8")) > 72

    response = client.post(
        "/api/v1/auth/signup", json={"email": "multibyte@example.com", "password": password}
    )
    assert response.status_code == 400


def _signup_and_get_tokens(client, email="sessions@example.com"):
    signup = client.post("/api/v1/auth/signup", json={"email": email, "password": "supersecret"})
    assert signup.status_code == 201
    return signup.json()


def test_list_sessions_returns_active_sessions_only(client):
    tokens = _signup_and_get_tokens(client)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    listing = client.get("/api/v1/auth/sessions", headers=headers)
    assert listing.status_code == 200
    sessions = listing.json()
    assert len(sessions) == 1
    assert set(sessions[0]) == {"id", "created_at", "expires_at"}

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 200

    # 로테이션으로 옛 토큰은 폐기됐으니 활성 세션은 여전히 1개여야 한다.
    listing_after_refresh = client.get("/api/v1/auth/sessions", headers=headers)
    assert len(listing_after_refresh.json()) == 1


def test_revoke_session_logs_out_that_refresh_token(client):
    tokens = _signup_and_get_tokens(client, email="revoke-session@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    session_id = client.get("/api/v1/auth/sessions", headers=headers).json()[0]["id"]

    revoke = client.delete(f"/api/v1/auth/sessions/{session_id}", headers=headers)
    assert revoke.status_code == 204

    listing = client.get("/api/v1/auth/sessions", headers=headers)
    assert listing.json() == []

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401


def test_revoke_session_rejects_other_users_session(client):
    tokens_a = _signup_and_get_tokens(client, email="session-a@example.com")
    tokens_b = _signup_and_get_tokens(client, email="session-b@example.com")
    headers_a = {"Authorization": f"Bearer {tokens_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tokens_b['access_token']}"}

    session_id_b = client.get("/api/v1/auth/sessions", headers=headers_b).json()[0]["id"]

    response = client.delete(f"/api/v1/auth/sessions/{session_id_b}", headers=headers_a)
    assert response.status_code == 404

    # 다른 사람의 세션은 여전히 살아있어야 한다.
    still_valid = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens_b["refresh_token"]})
    assert still_valid.status_code == 200


def test_revoke_session_rejects_unknown_session_id(client):
    tokens = _signup_and_get_tokens(client, email="unknown-session@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = client.delete(
        "/api/v1/auth/sessions/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert response.status_code == 404


def test_revoke_all_sessions_logs_out_everywhere(client):
    tokens = _signup_and_get_tokens(client, email="revoke-all@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 200
    new_tokens = refresh.json()

    revoke_all = client.delete("/api/v1/auth/sessions", headers=headers)
    assert revoke_all.status_code == 204

    listing = client.get("/api/v1/auth/sessions", headers=headers)
    assert listing.json() == []

    refresh_after = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert refresh_after.status_code == 401


def test_login_is_rate_limited(client, monkeypatch):
    monkeypatch.setenv("AUTH_RATE_LIMIT", "2/minute")
    get_settings.cache_clear()

    client.post(
        "/api/v1/auth/signup", json={"email": "ratelimit@example.com", "password": "supersecret"}
    )

    payload = {"email": "ratelimit@example.com", "password": "wrongpass"}
    first = client.post("/api/v1/auth/login", json=payload)
    second = client.post("/api/v1/auth/login", json=payload)
    third = client.post("/api/v1/auth/login", json=payload)

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429
    assert "Retry-After" in third.headers
    assert int(third.headers["Retry-After"]) >= 0
    # 다른 에러들과 같은 {"error": {"code", "message"}} 형태여야 한다 - slowapi
    # 기본 핸들러의 {"error": "문자열"} 포맷은 유일한 예외였는데 이제 통일됐다.
    body = third.json()
    assert body["error"]["code"] == "rate_limited"
    assert "Rate limit exceeded" in body["error"]["message"]
