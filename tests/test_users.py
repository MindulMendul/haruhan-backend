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

    asyncio.run(_run())
