import asyncio
import os
import tempfile
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.clock import utcnow_naive
from app.core.config import get_settings
from app.core.tokens import hash_refresh_token
from app.db.base import Base
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.services.auth_service import AuthService


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


def test_login_rejects_nonexistent_email(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "never-signed-up@example.com", "password": "whatever123"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_signup_duplicate_email_conflict(client):
    payload = {"email": "dup@example.com", "password": "supersecret"}
    first = client.post("/api/v1/auth/signup", json=payload)
    assert first.status_code == 201
    second = client.post("/api/v1/auth/signup", json=payload)
    assert second.status_code == 409


def test_concurrent_signup_with_same_email_yields_clean_conflict_not_crash():
    """signup()은 get_by_email로 "존재 안 함"을 확인한 뒤에야 insert한다
    (check-then-act) - 같은 이메일로 거의 동시에 두 요청이 오면 둘 다 그 확인을
    통과해버릴 수 있다. User.email의 DB unique 제약이 최종 방어선으로 남지만,
    그 위반(IntegrityError)을 서비스가 잡지 않으면 500으로 죽는다. 진짜 별개의
    커넥션 두 개가 필요해서(단일 커넥션을 공유하는 conftest의 :memory:+StaticPool
    픽스처는 두 세션이 사실상 직렬화되어 이 경쟁 자체가 재현되지 않는다),
    db_session.py 테스트에서 쓰는 것과 같은 파일 기반 SQLite로 별도 엔진을 만들어
    asyncio.gather로 실제로 동시에 호출해 재현한다 - 하나는 성공/하나는 깔끔한
    409로 끝나야 한다."""
    settings = get_settings()

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    url = f"sqlite+aiosqlite:///{path}"

    async def _run():
        engine = create_async_engine(url, pool_size=5, max_overflow=5)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)

            async with session_factory() as session_a, session_factory() as session_b:
                service_a = AuthService(session=session_a, settings=settings)
                service_b = AuthService(session=session_b, settings=settings)
                return await asyncio.gather(
                    service_a.signup(email="concurrent@example.com", password="supersecret"),
                    service_b.signup(email="concurrent@example.com", password="supersecret"),
                    return_exceptions=True,
                )
        finally:
            await engine.dispose()

    try:
        results = asyncio.run(_run())
    finally:
        if os.path.exists(path):
            os.unlink(path)

    successes = [r for r in results if not isinstance(r, Exception)]
    conflicts = [r for r in results if isinstance(r, HTTPException) and r.status_code == 409]
    other_errors = [
        r for r in results if isinstance(r, Exception) and not isinstance(r, HTTPException)
    ]

    assert len(successes) == 1
    assert len(conflicts) == 1
    assert other_errors == []


def test_signup_duplicate_email_different_case_is_conflict(client):
    """정규화 전에는 "Case@Example.com"과 "case@example.com"이 서로 다른 문자열이라
    User.email의 unique 제약을 피해가며 같은 메일함 소유자가 중복 계정을 만들 수
    있었다. 회원가입 시점에 소문자로 정규화되므로 대소문자만 다른 재가입도 409여야 한다."""
    first = client.post(
        "/api/v1/auth/signup", json={"email": "Case@Example.com", "password": "supersecret"}
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/auth/signup", json={"email": "case@EXAMPLE.com", "password": "supersecret"}
    )
    assert second.status_code == 409


def test_login_with_different_case_email_succeeds(client):
    signup = client.post(
        "/api/v1/auth/signup", json={"email": "MixedCase@Example.com", "password": "supersecret"}
    )
    assert signup.status_code == 201

    login = client.post(
        "/api/v1/auth/login", json={"email": "mixedcase@example.com", "password": "supersecret"}
    )
    assert login.status_code == 200


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


def test_refresh_is_rate_limited(client, monkeypatch):
    monkeypatch.setenv("AUTH_RATE_LIMIT", "2/minute")
    get_settings.cache_clear()

    payload = {"refresh_token": "never-issued-token"}
    first = client.post("/api/v1/auth/refresh", json=payload)
    second = client.post("/api/v1/auth/refresh", json=payload)
    third = client.post("/api/v1/auth/refresh", json=payload)

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429


def test_logout_is_rate_limited(client, monkeypatch):
    monkeypatch.setenv("AUTH_RATE_LIMIT", "2/minute")
    get_settings.cache_clear()

    payload = {"refresh_token": "never-issued-token"}
    first = client.post("/api/v1/auth/logout", json=payload)
    second = client.post("/api/v1/auth/logout", json=payload)
    third = client.post("/api/v1/auth/logout", json=payload)

    assert first.status_code == 204
    assert second.status_code == 204
    assert third.status_code == 429
