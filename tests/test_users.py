import asyncio
import os
import tempfile
import threading

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.password import hash_password
from app.db.base import Base
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
import app.services.user_service as user_service_module


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


def test_update_profile_rejects_oversized_current_password(client):
    """다른 모든 비밀번호 필드(SignupRequest.password 등)와 같이
    current_password도 72자 상한이 있어야 한다 - 없으면 터무니없이 긴 값이
    스키마 검증은 통과해 서비스 계층까지 내려가 "비밀번호가 틀렸습니다"(401)
    로 응답한다. 다른 필드들처럼 422로 일찍 거부하는지 확인한다."""
    tokens = _signup_and_get_tokens(client, email="update-oversized-pw@example.com")
    response = client.patch(
        "/api/v1/users/me",
        json={"email": "new@example.com", "current_password": "a" * 73},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 422


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


def test_concurrent_email_change_to_same_email_yields_clean_conflict_not_crash():
    """update_profile()도 get_by_email 확인 후 commit하는 check-then-act 구조라
    같은 경쟁 상태에 노출된다 - 서로 다른 두 계정이 거의 동시에 같은(아직 아무도
    안 쓰는) 이메일로 변경을 시도하면, DB unique 제약 위반이 그대로 새어나가지
    않고 하나는 성공/하나는 깔끔한 409로 끝나야 한다. signup()/upgrade_guest()의
    동시성 테스트와 같은 방식(파일 기반 SQLite + asyncio.gather)으로 재현한다."""
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
                hashed = hash_password("supersecret")
                user_a = await UserRepository(session_a).create(
                    email="account-a@example.com", hashed_password=hashed
                )
                await session_a.commit()
                user_b = await UserRepository(session_b).create(
                    email="account-b@example.com", hashed_password=hashed
                )
                await session_b.commit()

                service_a = UserService(session=session_a)
                service_b = UserService(session=session_b)
                return await asyncio.gather(
                    service_a.update_profile(
                        user=user_a,
                        email="race-rename@example.com",
                        password=None,
                        current_password="supersecret",
                    ),
                    service_b.update_profile(
                        user=user_b,
                        email="race-rename@example.com",
                        password=None,
                        current_password="supersecret",
                    ),
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


def test_update_password_revokes_existing_refresh_tokens(client):
    """비밀번호 변경은 보통 "계정이 뚫린 것 같다"는 의심에서 나오는 행동이다 -
    공격자가 refresh_token을 훔친 상태라면, 비밀번호만 바꾸고 기존
    refresh_token을 그대로 살려두면 공격자는 최대 refresh_token_expire_days
    (기본 14일)까지 그 토큰으로 계속 로그인 상태를 유지할 수 있어 비밀번호
    변경의 의미가 없어진다. 비밀번호 변경 전에 발급된 refresh_token이 변경
    후에는 (DELETE /auth/sessions 전체 로그아웃과 마찬가지로) 더 이상 쓸 수
    없는지 확인한다."""
    tokens = _signup_and_get_tokens(client, email="pw-revoke@example.com")

    update = client.patch(
        "/api/v1/users/me",
        json={"password": "newsupersecret", "current_password": "supersecret"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert update.status_code == 200

    refresh = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refresh.status_code == 401


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


def test_upgrade_guest_revokes_existing_refresh_tokens(client):
    """206라운드 다음(207라운드): 게스트는 hashed_password가 없어 승격 전까지
    자격 증명 검증 자체가 불가능하므로, refresh_token만 가지고 있으면 사실상
    계정을 통째로 쥐고 있는 것과 같다 - 그 refresh_token이 로그/공유 기기/XSS
    등으로 새어나갔더라도 승격 후 그대로 두면, 사용자가 방금 비밀번호를 설정해
    "이제 계정이 보호된다"고 믿는 것과 달리 공격자는 계속 그 refresh_token으로
    로그인 상태를 유지할 수 있다 - update_profile()의 비밀번호 변경 분기를
    검증하는 위 test_update_password_revokes_existing_refresh_tokens와 같은
    방식으로, 승격 전에 발급된 refresh_token이 승격 후에는 더 이상 쓸 수 없는지
    확인한다."""
    guest = client.post("/api/v1/auth/guest")
    assert guest.status_code == 201
    guest_tokens = guest.json()

    upgrade = client.post(
        "/api/v1/users/me/upgrade",
        json={"email": "upgrade-revoke@example.com", "password": "supersecret"},
        headers=_auth_headers(guest_tokens["access_token"]),
    )
    assert upgrade.status_code == 200

    refresh = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": guest_tokens["refresh_token"]}
    )
    assert refresh.status_code == 401


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


def test_delete_account_rejects_oversized_current_password(client):
    """다른 모든 비밀번호 필드(SignupRequest.password 등)와 같이
    current_password도 72자 상한이 있어야 한다 - 없으면 터무니없이 긴 값이
    스키마 검증은 통과해 서비스 계층까지 내려가 "비밀번호가 틀렸습니다"(401)
    로 응답한다. 다른 필드들처럼 422로 일찍 거부하는지 확인한다."""
    tokens = _signup_and_get_tokens(client, email="delete-oversized-pw@example.com")
    response = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"current_password": "a" * 73},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert response.status_code == 422


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


def test_update_profile_and_delete_account_hash_and_verify_password_off_the_event_loop_thread(
    db_session_factory, monkeypatch
):
    """bcrypt는 이 환경 기준 호출당 약 300ms가 걸리는 계산 비용이 큰 함수라,
    이벤트 루프에서 그대로 부르면 그 시간만큼 같은 워커의 다른 모든 동시 요청이
    멈춘다(90번 라운드에서 RAG 유사도 채점에 적용한 것과 같은 이유) -
    update_profile()의 verify_password(current_password 확인)/hash_password(비밀번호
    변경), delete_account()의 verify_password 호출이 실제로 메인(이벤트 루프)
    스레드가 아닌 스레드 풀에서 일어나는지 직접 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create(
                email="thread-check@example.com", hashed_password=hash_password("supersecret")
            )
            await session.commit()

            main_thread = threading.current_thread()
            call_threads: list[threading.Thread] = []

            original_hash_password = user_service_module.hash_password
            original_verify_password = user_service_module.verify_password

            def _tracking_hash_password(password):
                call_threads.append(threading.current_thread())
                return original_hash_password(password)

            def _tracking_verify_password(password, hashed_password):
                call_threads.append(threading.current_thread())
                return original_verify_password(password, hashed_password)

            monkeypatch.setattr(user_service_module, "hash_password", _tracking_hash_password)
            monkeypatch.setattr(user_service_module, "verify_password", _tracking_verify_password)

            service = UserService(session=session)
            await service.update_profile(
                user=user, email=None, password="newsecret", current_password="supersecret"
            )
            await service.delete_account(user=user, current_password="newsecret")

            # update_profile: verify_password(current_password 확인) + hash_password(비밀번호 변경)
            # delete_account: verify_password(current_password 확인)
            assert len(call_threads) == 3
            assert all(t is not main_thread for t in call_threads)


def test_update_profile_converts_concurrent_email_conflict_to_409(db_session_factory, monkeypatch):
    """update_profile()의 `get_by_email()` 확인과 `commit()` 사이에는(비밀번호를
    같이 바꾸는 경우 해싱 시간까지 포함해) 시간차가 있다 - 같은 이메일로 두
    프로필 변경/가입 요청이 거의 동시에 오면 둘 다 그 확인을 통과해버릴 수
    있고, 나중에 커밋하는 쪽만 유니크 제약 위반(IntegrityError)을 실제
    commit() 시점에야 만나게 된다. 진짜 동시 요청 타이밍 대신, `get_by_email`
    이 "그 확인 시점에는 충돌이 없었다"고 답하는 상황을 직접 재현한다(이미
    다른 사용자가 그 이메일로 커밋돼 있는데도 조회를 패치해 None을 반환하게
    함) - 새어나가는 처리되지 않은 예외(500) 대신, 정상적인 "이미 존재함"
    케이스와 같은 409로 변환되는지 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            users = UserRepository(session)
            await users.create(email="taken@example.com", hashed_password=hash_password("existing"))
            user = await users.create_guest()
            await session.commit()

            async def _fake_get_by_email(self, email):
                return None

            monkeypatch.setattr(UserRepository, "get_by_email", _fake_get_by_email)

            service = UserService(session=session)
            try:
                await service.update_profile(
                    user=user, email="taken@example.com", password=None, current_password=None
                )
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 409
    assert exc.detail == "Email already registered"


def test_update_profile_returns_401_when_account_deleted_during_request(db_session_factory, monkeypatch):
    """get_current_user 인증 확인과 이 commit() 사이에 다른 요청이
    UserService.delete_account()로(또는 159라운드가 추가한
    cleanup_stale_guest_accounts cron job으로) 이 계정을 지워버리면, ORM이 이미
    들고 있는 User 객체에 대한 UPDATE가 0행에 매치되어 StaleDataError가 난다 -
    143~171라운드가 자식 테이블 INSERT를 대상으로 고친 IntegrityError와는 다른
    경쟁으로, users 테이블 자신에 대한 UPDATE가 대상이다. get_by_email 조회
    "직후" 별도 세션에서 이 계정을 완전히 지우도록 만들어서 이 좁은 타이밍을
    결정적으로 재현한다."""

    async def _run():
        async with db_session_factory() as session:
            users = UserRepository(session)
            user = await users.create_guest()
            await session.commit()
            user_id = user.id

            original_get_by_email = UserRepository.get_by_email

            async def _deleting_get_by_email(self, email):
                async with db_session_factory() as session_b:
                    users_b = UserRepository(session_b)
                    target = await users_b.get_by_id(user_id)
                    await users_b.delete(target)
                    await session_b.commit()
                return await original_get_by_email(self, email)

            monkeypatch.setattr(UserRepository, "get_by_email", _deleting_get_by_email)

            service = UserService(session=session)
            try:
                await service.update_profile(
                    user=user, email="new@example.com", password=None, current_password=None
                )
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 401
    assert exc.detail == {"code": "invalid_token", "message": "Could not validate credentials"}


def test_update_profile_with_password_change_returns_401_when_account_deleted_during_request(
    db_session_factory, monkeypatch
):
    """207라운드: 위 테스트와 같은 경쟁을, 이메일뿐 아니라 비밀번호까지 함께
    바꾸는 경우로 재현한다. revoke_all_for_user()는 내부에서 session.flush()를
    호출하는데, 이 flush()가 이 계정이 이미 지워진 상태에서 위쪽 get_by_email
    직후 반영된 user.email/hashed_password의 dirty 상태를 함께 내보내면서 그
    자체로 StaleDataError를 낼 수 있다 - 이 fixture 값이 commit()을 감싸는
    try/except보다 앞에서(207라운드가 고치기 전에는 실제로 그 순서였다) 나가면,
    새는 StaleDataError가 이 메서드 밖으로 그대로 전파돼 처리되지 않은 예외가
    된다. revoke_all_for_user()도 반드시 같은 try 안, commit() 바로 앞에서
    호출해야 함을 확인한다."""

    async def _run():
        async with db_session_factory() as session:
            users = UserRepository(session)
            user = await users.create_guest()
            await session.commit()
            user_id = user.id

            original_get_by_email = UserRepository.get_by_email

            async def _deleting_get_by_email(self, email):
                async with db_session_factory() as session_b:
                    users_b = UserRepository(session_b)
                    target = await users_b.get_by_id(user_id)
                    await users_b.delete(target)
                    await session_b.commit()
                return await original_get_by_email(self, email)

            monkeypatch.setattr(UserRepository, "get_by_email", _deleting_get_by_email)

            service = UserService(session=session)
            try:
                await service.update_profile(
                    user=user,
                    email="new-with-pw@example.com",
                    password="supersecret",
                    current_password=None,
                )
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 401
    assert exc.detail == {"code": "invalid_token", "message": "Could not validate credentials"}


def test_upgrade_guest_returns_401_when_account_deleted_during_request(db_session_factory, monkeypatch):
    """update_profile()의 위 테스트와 같은 경쟁을 upgrade_guest()에서도 재현한다 -
    이 메서드는 email 지정 여부와 무관하게 항상 get_by_email을 부른다."""

    async def _run():
        async with db_session_factory() as session:
            users = UserRepository(session)
            user = await users.create_guest()
            await session.commit()
            user_id = user.id

            original_get_by_email = UserRepository.get_by_email

            async def _deleting_get_by_email(self, email):
                async with db_session_factory() as session_b:
                    users_b = UserRepository(session_b)
                    target = await users_b.get_by_id(user_id)
                    await users_b.delete(target)
                    await session_b.commit()
                return await original_get_by_email(self, email)

            monkeypatch.setattr(UserRepository, "get_by_email", _deleting_get_by_email)

            service = UserService(session=session)
            try:
                await service.upgrade_guest(user=user, email="new@example.com", password="supersecret")
                return None
            except HTTPException as exc:
                return exc

    exc = asyncio.run(_run())

    assert exc is not None
    assert exc.status_code == 401
    assert exc.detail == {"code": "invalid_token", "message": "Could not validate credentials"}
