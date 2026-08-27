import asyncio
import os
import tempfile
import threading
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.clock import utcnow_naive
from app.core.config import get_settings
from app.core.password import hash_password
from app.core.tokens import hash_refresh_token, refresh_token_expiry
from app.db.base import Base
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
import app.services.auth_service as auth_service_module


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


def test_refresh_rejects_token_over_max_length(client):
    """다른 사용자 입력 필드들과 마찬가지로 refresh_token에도 명시적 상한이 있다 -
    상한을 넘으면 (알 수 없는 토큰이라 401이 아니라) 스키마 검증에서 바로 422로
    거부돼야 한다."""
    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "a" * 513}
    )
    assert response.status_code == 422


def test_logout_rejects_token_over_max_length(client):
    response = client.post(
        "/api/v1/auth/logout", json={"refresh_token": "a" * 513}
    )
    assert response.status_code == 422


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


def test_revoke_if_active_rejects_second_writer(db_session_factory):
    """refresh()는 "제시된 토큰이 아직 안 폐기됐는가"를 확인한 뒤에야 실제로
    폐기하는 check-then-act 구조였다 - 같은 토큰으로 거의 동시에 온 두 요청이
    둘 다 그 확인을 통과해버리면, 일반 UPDATE로는 둘 다 폐기에 성공해 하나의
    토큰 소비로 두 개의 유효한 세션이 나올 수 있었다(로테이션/재사용 탐지가
    막으려던 상황을 그대로 허용하는 셈). 이를 막는 compare-and-swap인
    revoke_if_active()를 같은 토큰에 순서대로 두 번 호출해서, 첫 번째만
    성공(True)하고 두 번째는 실패(False)하는지 직접 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            repo = RefreshTokenRepository(session)
            token = await repo.create(
                user_id=user.id,
                token_hash=hash_refresh_token("raw-token-for-cas-test"),
                expires_at=refresh_token_expiry(get_settings()),
            )
            await session.commit()

            first = await repo.revoke_if_active(token.id)
            second = await repo.revoke_if_active(token.id)
            await session.commit()
            return first, second

    first, second = asyncio.run(_run())

    assert first is True
    assert second is False


def test_concurrent_refresh_of_same_token_is_detected_and_revokes_all_sessions(
    db_session_factory, monkeypatch
):
    """위 CAS 자체가 아니라, refresh() 서비스 로직이 CAS 실패를 실제로 "재사용
    의심"과 동일하게 처리하는지 검증한다. 진짜 asyncio.gather 동시 재현은 이
    흐름이 폐기(UPDATE) + 발급(INSERT) + 커밋까지 여러 단계를 거치는 다중 쓰기
    트랜잭션이라 SQLite 파일 락 모델에서 결정적이지 않다(54번 라운드
    interview_practice 레이스 테스트에서 이미 확인한 것과 같은 한계) - 그래서
    "같은 토큰으로 동시에 온 다른 요청이 이미 폐기+로테이션까지 끝냈다"는 상황을
    revoke_if_active 호출 지점에 결정적으로 주입한다. 패자가 되는 이 요청은
    이미 재사용된 토큰을 만난 것과 똑같이 401을 받고, 승자가 방금 발급받은
    최신 토큰을 포함해 그 유저의 모든 활성 세션이 강제로 끊겨야 한다."""

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            settings = get_settings()
            raw_token = "raw-token-for-refresh-race-test"
            await RefreshTokenRepository(session).create(
                user_id=user.id,
                token_hash=hash_refresh_token(raw_token),
                expires_at=refresh_token_expiry(settings),
            )
            await session.commit()

            class RaceInjectingRefreshTokenRepository(RefreshTokenRepository):
                async def revoke_if_active(self, token_id):
                    # "동시에" 도착한 다른 요청(승자)이 이 CAS 호출 직전에 이미
                    # 같은 토큰을 폐기하고 자기 몫의 새 토큰 쌍까지 발급받았다고
                    # 가정한다.
                    await super().revoke_if_active(token_id)
                    await self.create(
                        user_id=user.id,
                        token_hash=hash_refresh_token("winner-issued-token"),
                        expires_at=refresh_token_expiry(settings),
                    )
                    # 승자가 이미 폐기했으니, 지금 이 (패자) 호출은 실패해야 한다.
                    return await super().revoke_if_active(token_id)

            import app.services.auth_service as auth_service_module

            monkeypatch.setattr(
                auth_service_module,
                "RefreshTokenRepository",
                RaceInjectingRefreshTokenRepository,
            )
            service = AuthService(session=session, settings=settings)

            try:
                await service.refresh(raw_token)
                caught = None
            except HTTPException as exc:
                caught = exc

            remaining = await RefreshTokenRepository(session).list_active_for_user(
                user.id, limit=20, offset=0
            )
            return caught, remaining

    caught, remaining = asyncio.run(_run())

    assert caught is not None
    assert caught.status_code == 401
    assert remaining == []


def test_login_returns_401_when_account_deleted_during_login(db_session_factory, monkeypatch):
    """get_by_email() 확인과 그 뒤 bcrypt 비교로 늘어난 시간차 사이에 다른 요청이
    UserService.delete_account()로 이 계정을 지워버리면, _issue_tokens()의
    refresh_token INSERT가(RefreshToken.user_id는 nullable=False FK) IntegrityError로
    실패한다 - 잡지 않으면 로그인이라는 이 앱에서 가장 자주 타는 경로가 그대로
    처리되지 않은 예외(500)로 새어나간다. get_by_email이 반환하기 직전 별도
    세션에서 그 계정을 실제로 지우도록 만들어 이 타이밍을 결정적으로 재현한다."""

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create(
                email="disappearing@example.com", hashed_password=hash_password("supersecret")
            )
            await session.commit()
            user_id = user.id

            class DeletingUserRepository(UserRepository):
                async def get_by_email(self, email):
                    result = await super().get_by_email(email)
                    async with db_session_factory() as session_b:
                        users_b = UserRepository(session_b)
                        target = await users_b.get_by_id(user_id)
                        await users_b.delete(target)
                        await session_b.commit()
                    return result

            monkeypatch.setattr(auth_service_module, "UserRepository", DeletingUserRepository)

            settings = get_settings()
            service = AuthService(session=session, settings=settings)

            try:
                await service.login(email="disappearing@example.com", password="supersecret")
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 401


def test_refresh_returns_401_when_account_deleted_during_refresh(db_session_factory, monkeypatch):
    """refresh()도 login()과 같은 이유로 취약하다 - revoke_if_active()로 옛
    토큰을 성공적으로 폐기한 직후, _issue_tokens()의 INSERT 전에 다른 요청이
    이 계정을 지워버리면 같은 IntegrityError가 새어나간다. revoke_if_active가
    반환하기 직전 별도 세션에서 계정을 지우도록 만들어 재현한다."""

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()
            user_id = user.id

            settings = get_settings()
            raw_token = "raw-token-for-account-deleted-during-refresh"
            await RefreshTokenRepository(session).create(
                user_id=user.id,
                token_hash=hash_refresh_token(raw_token),
                expires_at=refresh_token_expiry(settings),
            )
            await session.commit()

            class DeletingRefreshTokenRepository(RefreshTokenRepository):
                async def revoke_if_active(self, token_id):
                    result = await super().revoke_if_active(token_id)
                    async with db_session_factory() as session_b:
                        users_b = UserRepository(session_b)
                        target = await users_b.get_by_id(user_id)
                        await users_b.delete(target)
                        await session_b.commit()
                    return result

            monkeypatch.setattr(
                auth_service_module, "RefreshTokenRepository", DeletingRefreshTokenRepository
            )
            service = AuthService(session=session, settings=settings)

            try:
                await service.refresh(raw_token)
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 401


def test_refresh_returns_401_when_account_deleted_before_user_lookup(db_session_factory, monkeypatch):
    """refresh()가 계정 삭제 경쟁에 취약해질 수 있는 지점이 하나 더 있다 - 위 두
    테스트보다 더 이른 시점(stored refresh_token을 읽은 직후, get_by_id() 전)에
    계정이 지워지면, User.delete()의 CASCADE로 이 refresh_token row 자체도
    이미 함께 지워진 뒤라 get_by_id()가 그냥 None을 반환한다(IntegrityError가
    아니라). refresh()는 이미 `if user is None: raise _INVALID_REFRESH_TOKEN`으로
    이 경우를 올바르게 처리하고 있었지만, 이 정확한 타이밍을 재현하는 테스트가
    없어 이 분기가 커버되지 않고 있었다 - 위 두 테스트가 다루는 "계정 삭제 경쟁"
    조사의 연장선에서 함께 메운다. get_by_hash가 반환하기 직전 별도 세션에서
    계정을 지우도록 만들어 재현한다."""

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()
            user_id = user.id

            settings = get_settings()
            raw_token = "raw-token-for-account-deleted-before-lookup"
            await RefreshTokenRepository(session).create(
                user_id=user.id,
                token_hash=hash_refresh_token(raw_token),
                expires_at=refresh_token_expiry(settings),
            )
            await session.commit()

            class DeletingRefreshTokenRepository(RefreshTokenRepository):
                async def get_by_hash(self, token_hash):
                    result = await super().get_by_hash(token_hash)
                    async with db_session_factory() as session_b:
                        users_b = UserRepository(session_b)
                        target = await users_b.get_by_id(user_id)
                        await users_b.delete(target)
                        await session_b.commit()
                    return result

            monkeypatch.setattr(
                auth_service_module, "RefreshTokenRepository", DeletingRefreshTokenRepository
            )
            service = AuthService(session=session, settings=settings)

            try:
                await service.refresh(raw_token)
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 401


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


def test_signup_and_login_hash_and_verify_password_off_the_event_loop_thread(
    db_session_factory, monkeypatch
):
    """bcrypt는 이 환경 기준 호출당 약 300ms가 걸리는 계산 비용이 큰 함수라,
    이벤트 루프에서 그대로 부르면 그 시간만큼 같은 워커의 다른 모든 동시 요청이
    멈춘다(90번 라운드에서 RAG 유사도 채점에 적용한 것과 같은 이유) - signup()의
    hash_password, login()의 verify_password 호출이 실제로 메인(이벤트 루프)
    스레드가 아닌 스레드 풀에서 일어나는지 직접 확인한다."""
    settings = get_settings()

    async def _run():
        async with db_session_factory() as session:
            main_thread = threading.current_thread()
            call_threads: list[threading.Thread] = []

            original_hash_password = auth_service_module.hash_password
            original_verify_password = auth_service_module.verify_password

            def _tracking_hash_password(password):
                call_threads.append(threading.current_thread())
                return original_hash_password(password)

            def _tracking_verify_password(password, hashed_password):
                call_threads.append(threading.current_thread())
                return original_verify_password(password, hashed_password)

            monkeypatch.setattr(auth_service_module, "hash_password", _tracking_hash_password)
            monkeypatch.setattr(auth_service_module, "verify_password", _tracking_verify_password)

            service = AuthService(session=session, settings=settings)
            await service.signup(email="thread-check@example.com", password="supersecret")
            await service.login(email="thread-check@example.com", password="supersecret")

            # signup -> hash_password 1회, login -> verify_password 1회
            assert len(call_threads) == 2
            assert all(t is not main_thread for t in call_threads)

    asyncio.run(_run())


def test_list_sessions_pagination(client):
    """로그인할 때마다 새 refresh token이 발급되고 명시적으로 로그아웃하지
    않는 한 폐기되지 않는다(여러 기기 동시 로그인 지원) - 같은 계정으로 반복
    로그인하면 활성 세션이 계속 쌓인다. list_quizzes 등 다른 목록 API와
    동일하게 limit/offset을 받고 X-Total-Count로 총 개수를 알려줘야 한다."""
    email = "sessions-pagination@example.com"
    password = "supersecret"
    signup = client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    assert signup.status_code == 201
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    # signup 자체가 이미 세션 1개를 만들었으니, 로그인 3번을 더해 총 4개로 만든다.
    for _ in range(3):
        login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert login.status_code == 200

    first_page = client.get("/api/v1/auth/sessions?limit=2&offset=0", headers=headers)
    assert first_page.status_code == 200
    assert len(first_page.json()) == 2
    assert first_page.headers["X-Total-Count"] == "4"

    second_page = client.get("/api/v1/auth/sessions?limit=2&offset=2", headers=headers)
    assert len(second_page.json()) == 2

    first_ids = {s["id"] for s in first_page.json()}
    second_ids = {s["id"] for s in second_page.json()}
    assert first_ids.isdisjoint(second_ids)


def test_list_sessions_is_rate_limited(client, monkeypatch):
    """다른 /auth/* 라우트(signup/login/refresh/logout/revoke_session/
    revoke_all_sessions)는 전부 @limiter.limit()이 걸려 있는데
    GET /sessions만 레이트리밋이 전혀 없었다."""
    monkeypatch.setenv("AUTH_RATE_LIMIT", "2/minute")
    get_settings.cache_clear()
    tokens = _signup_and_get_tokens(client, email="sessions-ratelimit@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    first = client.get("/api/v1/auth/sessions", headers=headers)
    second = client.get("/api/v1/auth/sessions", headers=headers)
    third = client.get("/api/v1/auth/sessions", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
