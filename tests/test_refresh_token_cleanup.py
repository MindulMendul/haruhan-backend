import asyncio
from datetime import timedelta

from app.core.clock import utcnow_naive
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


def test_delete_expired_removes_only_expired_tokens(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            tokens = RefreshTokenRepository(session)
            expired = await tokens.create(
                user_id=user.id, token_hash="expired-hash", expires_at=utcnow_naive() - timedelta(days=1)
            )
            valid = await tokens.create(
                user_id=user.id, token_hash="valid-hash", expires_at=utcnow_naive() + timedelta(days=1)
            )
            await session.commit()

            deleted_count = await tokens.delete_expired()
            assert deleted_count == 1

            assert await tokens.get_by_hash(expired.token_hash) is None
            assert await tokens.get_by_hash(valid.token_hash) is not None

    asyncio.run(_run())


def test_delete_expired_removes_expired_even_if_revoked(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            tokens = RefreshTokenRepository(session)
            token = await tokens.create(
                user_id=user.id, token_hash="revoked-expired-hash", expires_at=utcnow_naive() - timedelta(days=1)
            )
            await tokens.revoke(token)
            await session.commit()

            deleted_count = await tokens.delete_expired()
            assert deleted_count == 1
            assert await tokens.get_by_hash("revoked-expired-hash") is None

    asyncio.run(_run())


def test_delete_expired_returns_zero_when_nothing_to_delete(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            await session.commit()

            tokens = RefreshTokenRepository(session)
            await tokens.create(
                user_id=user.id, token_hash="still-valid-hash", expires_at=utcnow_naive() + timedelta(days=1)
            )
            await session.commit()

            assert await tokens.delete_expired() == 0

    asyncio.run(_run())
