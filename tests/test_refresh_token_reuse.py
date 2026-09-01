import asyncio
from datetime import timedelta

from app.core.clock import utcnow_naive
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


def test_revoke_all_for_user_revokes_only_that_users_active_tokens(db_session_factory):
    async def _run():
        async with db_session_factory() as session:
            user = await UserRepository(session).create_guest()
            other_user = await UserRepository(session).create_guest()
            await session.commit()

            tokens = RefreshTokenRepository(session)
            await tokens.create(
                user_id=user.id, token_hash="a-hash", expires_at=utcnow_naive() + timedelta(days=1)
            )
            await tokens.create(
                user_id=user.id, token_hash="b-hash", expires_at=utcnow_naive() + timedelta(days=1)
            )
            already_revoked = await tokens.create(
                user_id=user.id, token_hash="c-hash", expires_at=utcnow_naive() + timedelta(days=1)
            )
            await tokens.revoke(already_revoked)
            revoked_at_before = already_revoked.revoked_at
            await tokens.create(
                user_id=other_user.id,
                token_hash="other-hash",
                expires_at=utcnow_naive() + timedelta(days=1),
            )
            await session.commit()

            await tokens.revoke_all_for_user(user.id)
            await session.commit()

            a = await tokens.get_by_hash("a-hash")
            b = await tokens.get_by_hash("b-hash")
            c = await tokens.get_by_hash("c-hash")
            other = await tokens.get_by_hash("other-hash")

            assert a.revoked_at is not None
            assert b.revoked_at is not None
            # 이미 폐기돼 있던 토큰은 건드리지 않는다 (revoked_at이 최신 시각으로 덮어써지지 않음).
            assert c.revoked_at == revoked_at_before
            assert other.revoked_at is None

    asyncio.run(_run())
