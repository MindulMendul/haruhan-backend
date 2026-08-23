import asyncio
import os
import tempfile

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService


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


def test_guest_can_upgrade_to_real_account(client):
    guest = client.post("/api/v1/auth/guest").json()

    upgrade = client.post(
        "/api/v1/users/me/upgrade",
        json={"email": "upgraded@example.com", "password": "supersecret"},
        headers=_auth_headers(guest["access_token"]),
    )
    assert upgrade.status_code == 200
    body = upgrade.json()
    assert body["email"] == "upgraded@example.com"
    assert body["is_guest"] is False

    login = client.post(
        "/api/v1/auth/login", json={"email": "upgraded@example.com", "password": "supersecret"}
    )
    assert login.status_code == 200


def test_guest_upgrade_keeps_existing_data(client):
    guest = client.post("/api/v1/auth/guest").json()
    client.post(
        "/api/v1/study/sessions",
        json={"title": "게스트일 때 만든 세션"},
        headers=_auth_headers(guest["access_token"]),
    )

    upgrade = client.post(
        "/api/v1/users/me/upgrade",
        json={"email": "keepdata@example.com", "password": "supersecret"},
        headers=_auth_headers(guest["access_token"]),
    )
    assert upgrade.status_code == 200

    sessions = client.get("/api/v1/study/sessions", headers=_auth_headers(guest["access_token"]))
    assert len(sessions.json()) == 1
    assert sessions.json()[0]["title"] == "게스트일 때 만든 세션"


def test_guest_upgrade_rejects_email_already_taken(client):
    client.post("/api/v1/auth/signup", json={"email": "taken@example.com", "password": "supersecret"})
    guest = client.post("/api/v1/auth/guest").json()

    upgrade = client.post(
        "/api/v1/users/me/upgrade",
        json={"email": "taken@example.com", "password": "supersecret"},
        headers=_auth_headers(guest["access_token"]),
    )
    assert upgrade.status_code == 409


def test_real_account_cannot_use_upgrade_endpoint(client):
    tokens = client.post(
        "/api/v1/auth/signup", json={"email": "already-real@example.com", "password": "supersecret"}
    ).json()

    upgrade = client.post(
        "/api/v1/users/me/upgrade",
        json={"email": "someone-else@example.com", "password": "newpassword"},
        headers=_auth_headers(tokens["access_token"]),
    )
    assert upgrade.status_code == 409


def test_concurrent_upgrade_to_same_email_yields_clean_conflict_not_crash():
    """upgrade_guest()도 signup()과 같은 check-then-act(get_by_email 확인 후
    commit) 구조라 같은 경쟁 상태에 노출된다 - 서로 다른 두 게스트가 거의 동시에
    같은 이메일로 업그레이드를 시도하면, DB unique 제약 위반이 그대로 새어나가지
    않고 하나는 성공/하나는 깔끔한 409로 끝나야 한다. 진짜 별개의 커넥션이
    필요해서 test_auth.py의 동시 가입 테스트와 같은 방식(파일 기반 SQLite +
    asyncio.gather)으로 재현한다."""
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
                guest_a = await UserRepository(session_a).create_guest()
                await session_a.commit()
                guest_b = await UserRepository(session_b).create_guest()
                await session_b.commit()

                service_a = UserService(session=session_a)
                service_b = UserService(session=session_b)
                return await asyncio.gather(
                    service_a.upgrade_guest(
                        user=guest_a, email="race-upgrade@example.com", password="supersecret"
                    ),
                    service_b.upgrade_guest(
                        user=guest_b, email="race-upgrade@example.com", password="supersecret"
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
