from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import guest_conversions_total
from app.core.password import PasswordTooLongError, hash_password, verify_password
from app.db.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)

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
            # 비밀번호를 바꾸는 건 보통 "계정이 뚫린 것 같다"는 의심에서 나오는
            # 행동인데, 여기서 refresh token을 그대로 두면 공격자가 훔친 refresh
            # token으로 최대 refresh_token_expire_days(기본 14일)까지 계속
            # 로그인 상태를 유지할 수 있어 비밀번호 변경의 의미가 없어진다 -
            # auth_service.py가 재사용 탐지/전체 로그아웃에 이미 쓰고 있는
            # revoke_all_for_user()로 이 계정의 모든 refresh token을 함께
            # 폐기한다(지금 이 요청을 보낸 클라이언트 자신의 refresh token도
            # 포함 - access token만으로는 어느 refresh token이 이 세션 것인지
            # 구분할 수 없어 DELETE /auth/sessions 전체 로그아웃과 똑같이
            # 다시 로그인해야 한다).
            await self._refresh_tokens.revoke_all_for_user(user.id)

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
