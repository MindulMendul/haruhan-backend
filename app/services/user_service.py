from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.password import PasswordTooLongError, hash_password, verify_password
from app.db.models.user import User
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def update_profile(
        self,
        user: User,
        email: str | None,
        password: str | None,
        current_password: str | None,
    ) -> User:
        if current_password is not None and not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="현재 비밀번호가 일치하지 않습니다."
            )

        if email is not None and email != user.email:
            existing = await self._users.get_by_email(email)
            if existing is not None and existing.id != user.id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
            user.email = email

        if password is not None:
            try:
                user.hashed_password = hash_password(password)
            except PasswordTooLongError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        await self._session.commit()
        return user
