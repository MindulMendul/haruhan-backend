import asyncio
from datetime import timedelta

from app.core.clock import utcnow_naive
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.study_session_repository import StudySessionRepository
from app.repositories.user_repository import UserRepository


def test_delete_stale_guests_removes_guest_with_no_active_refresh_token(db_session_factory):
    """게스트는 email/password가 없어 활성 refresh token이 전부 사라지면 그 계정에
    다시 접근할 방법이 아예 없다(docs/FRONTEND_INTEGRATION.md) - 만료되거나
    폐기된 토큰만 남은 게스트는 정리 대상이어야 한다."""

    async def _run():
        async with db_session_factory() as session:
            users = UserRepository(session)
            tokens = RefreshTokenRepository(session)

            guest = await users.create_guest()
            expired = await tokens.create(
                user_id=guest.id, token_hash="expired-hash", expires_at=utcnow_naive() - timedelta(days=1)
            )
            revoked = await tokens.create(
                user_id=guest.id, token_hash="revoked-hash", expires_at=utcnow_naive() + timedelta(days=1)
            )
            await tokens.revoke(revoked)
            await session.commit()
            del expired

            deleted = await users.delete_stale_guests(utcnow_naive())
            await session.commit()

            assert deleted == 1
            assert await users.get_by_id(guest.id) is None

    asyncio.run(_run())


def test_delete_stale_guests_cascades_to_owned_data(db_session_factory):
    """User row만 지워도 ON DELETE CASCADE로 학습챗 세션 등 딸린 데이터가
    함께 지워지는지 확인한다 - delete()의 기존 보장을 delete_stale_guests()도
    똑같이 물려받는지가 핵심이다."""

    async def _run():
        async with db_session_factory() as session:
            users = UserRepository(session)
            sessions = StudySessionRepository(session)
            tokens = RefreshTokenRepository(session)

            guest = await users.create_guest()
            study_session = await sessions.create(user_id=guest.id, title="세션", model="qwen2.5:3b")
            expired_token = await tokens.create(
                user_id=guest.id, token_hash="expired-hash-2", expires_at=utcnow_naive() - timedelta(days=1)
            )
            await session.commit()
            del expired_token

            deleted = await users.delete_stale_guests(utcnow_naive())
            await session.commit()

            assert deleted == 1
            assert await sessions.get_for_user(study_session.id, guest.id) is None

    asyncio.run(_run())


def test_delete_stale_guests_keeps_guest_with_active_refresh_token(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            users = UserRepository(session)
            tokens = RefreshTokenRepository(session)

            guest = await users.create_guest()
            await tokens.create(
                user_id=guest.id, token_hash="active-hash", expires_at=utcnow_naive() + timedelta(days=1)
            )
            await session.commit()

            deleted = await users.delete_stale_guests(utcnow_naive())
            await session.commit()

            assert deleted == 0
            assert await users.get_by_id(guest.id) is not None

    asyncio.run(_run())


def test_delete_stale_guests_never_touches_real_accounts(db_session_factory):
    """실계정은 email이 있어 refresh token이 전부 만료/폐기돼도(비밀번호로
    언제든 재로그인 가능하므로) 정리 대상이 아니어야 한다."""

    async def _run():
        async with db_session_factory() as session:
            users = UserRepository(session)
            tokens = RefreshTokenRepository(session)

            real_user = await users.create(email="real@example.com", hashed_password="hashed")
            expired = await tokens.create(
                user_id=real_user.id, token_hash="real-expired-hash", expires_at=utcnow_naive() - timedelta(days=1)
            )
            await session.commit()
            del expired

            deleted = await users.delete_stale_guests(utcnow_naive())
            await session.commit()

            assert deleted == 0
            assert await users.get_by_id(real_user.id) is not None

    asyncio.run(_run())
