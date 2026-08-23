from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import guest_conversions_total
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
        if current_password is not None:
            # 게스트 계정은 hashed_password가 없어 비교 자체가 불가능하다 (아직 계정 전환 기능 없음).
            if user.hashed_password is None or not verify_password(current_password, user.hashed_password):
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

        # 위 get_by_email 확인과 이 commit 사이에는(비밀번호 해싱 시간까지 포함해)
        # 시간차가 있다 - 같은 이메일로 두 프로필 변경/가입 요청이 동시에 오면 둘 다
        # 통과해버릴 수 있다. DB unique 제약 위반(IntegrityError)이 그대로 새어나가면
        # 나머지 흐름과 다르게 처리되지 않은 예외(500)가 되므로, 정상적인 "이미
        # 존재함" 케이스와 같은 409로 변환한다.
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            ) from None
        return user

    async def upgrade_guest(self, user: User, email: str, password: str) -> User:
        """게스트 계정을 email/password가 있는 실계정으로 승격시킨다.

        이미 hashed_password가 있는(=실계정인) 사용자가 호출하면 거부한다 - 그 경우는
        current_password 확인이 필요한 update_profile()을 대신 써야 한다.
        """
        if user.hashed_password is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이미 실계정입니다.")

        existing = await self._users.get_by_email(email)
        if existing is not None and existing.id != user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        try:
            user.hashed_password = hash_password(password)
        except PasswordTooLongError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        user.email = email

        # update_profile()과 같은 이유(check-then-act 경쟁 상태)로, DB unique
        # 제약 위반이 그대로 새어나가지 않도록 같은 409로 변환한다.
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            ) from None
        guest_conversions_total.inc()
        return user

    async def delete_account(self, user: User, current_password: str | None) -> None:
        """계정과 연관 데이터(학습챗/퀴즈/면접연습/면접복기/RAG 색인/refresh
        token) 전체를 영구 삭제한다. User row만 지우면 나머지는 DB의
        ON DELETE CASCADE로 함께 지워진다.

        실계정은 탈취된 access token만으로 계정을 통째로 지우지 못하도록
        현재 비밀번호로 재확인해야 한다. 게스트는 hashed_password가 없어
        비교 자체가 불가능하므로 확인 없이 진행한다.
        """
        if user.hashed_password is not None:
            if current_password is None or not verify_password(current_password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="현재 비밀번호가 일치하지 않습니다."
                )

        await self._users.delete(user)
        await self._session.commit()
