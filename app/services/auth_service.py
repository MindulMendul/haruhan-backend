import asyncio
import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.clock import utcnow_naive
from app.core.config import Settings
from app.core.metrics import user_signups_total
from app.core.password import PasswordTooLongError, hash_password, verify_password
from app.core.tokens import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
)
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse

_INVALID_CREDENTIALS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"code": "invalid_credentials", "message": "Invalid email or password"},
)
_INVALID_REFRESH_TOKEN = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"code": "invalid_refresh_token", "message": "Invalid refresh token"},
)
_SESSION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail={"code": "session_not_found", "message": "Session not found"},
)


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)

    async def signup(self, email: str, password: str) -> TokenResponse:
        existing = await self._users.get_by_email(email)
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

        try:
            # bcrypt는 의도적으로 계산 비용이 큰(이 환경 기준 호출당 약 300ms) 함수라,
            # 이벤트 루프에서 그대로 부르면 그 시간만큼 같은 워커의 다른 모든 동시
            # 요청(다른 사용자의 요청, 진행 중인 WebSocket 스트림 등)이 멈춘다 -
            # 90번 라운드에서 RAG 유사도 채점에 적용한 것과 같은 이유로, 매 로그인/
            # 가입/비밀번호 변경마다 반드시 거치는 이 CPU 바운드 계산을 스레드
            # 풀로 위임한다.
            hashed = await asyncio.to_thread(hash_password, password)
        except PasswordTooLongError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        # 위 get_by_email 확인과 아래 insert 사이에는 시간차가 있다(check-then-act) -
        # 같은 이메일로 거의 동시에 두 번 가입 요청이 오면 둘 다 "존재 안 함"을 보고
        # 통과해버릴 수 있다. User.email의 DB unique 제약이 최종 방어선으로 남아있어
        # 데이터가 잘못 들어가진 않지만, 그 위반이 IntegrityError로 그대로 새어나가면
        # 나머지 흐름과 다르게 처리되지 않은 예외(500)가 되어버린다 - 정상적인
        # "이미 존재함" 케이스와 똑같이 409로 변환한다.
        try:
            user = await self._users.create(email=email, hashed_password=hashed)
            tokens = await self._issue_tokens(user)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
            ) from None
        user_signups_total.inc()
        return tokens

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self._users.get_by_email(email)
        # 게스트는 email이 없어 여기 도달할 일이 없지만(hashed_password도 항상 None),
        # 방어적으로 명시 검사한다. verify_password는 이메일이 없어도(hashed_password
        # 인자가 None이어도) 항상 호출해야 한다 - `or`로 단축 평가해 존재하지 않는
        # 이메일에서 곧바로 반환해버리면, bcrypt 비교를 건너뛴 만큼 응답이 빨라져서
        # 응답 시간만으로 이메일 가입 여부를 추측할 수 있게 된다(타이밍 공격).
        hashed_password = user.hashed_password if user is not None else None
        password_matches = await asyncio.to_thread(verify_password, password, hashed_password)
        if user is None or hashed_password is None or not password_matches:
            raise _INVALID_CREDENTIALS

        # get_by_email 확인(과 그 뒤 bcrypt 비교로 늘어난 시간차) 사이에 다른 요청이
        # UserService.delete_account()로 이 계정을 지워버리면(RefreshToken.user_id는
        # nullable=False FK), _issue_tokens()의 refresh_token INSERT가
        # IntegrityError로 실패한다 - 잡지 않으면 로그인이라는, 이 앱에서 가장 자주
        # 타는 경로가 그대로 처리되지 않은 예외(500)로 새어나간다. "계정이 이미
        # 없어졌다"는 사실상 잘못된 자격증명과 같은 취급이라 같은 401로 변환한다.
        try:
            tokens = await self._issue_tokens(user)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise _INVALID_CREDENTIALS from None
        return tokens

    async def refresh(self, refresh_token: str) -> TokenResponse:
        token_hash = hash_refresh_token(refresh_token)
        stored = await self._refresh_tokens.get_by_hash(token_hash)
        if stored is None:
            raise _INVALID_REFRESH_TOKEN

        if stored.revoked_at is not None:
            # 이미 폐기된(=한 번 로테이션됐거나 로그아웃된) 토큰이 다시 제시됐다 - 탈취
            # 의심 신호다. 정상 사용자라면 로테이션된 최신 토큰을 쓰고 있을 테니, 이
            # 낡은 토큰이 다시 나타났다는 건 누군가 훔쳐 쓰고 있을 가능성이 크다.
            # 공격자와 정상 사용자 모두 강제 로그아웃시켜 세션을 안전한 상태로 되돌린다.
            await self._refresh_tokens.revoke_all_for_user(stored.user_id)
            await self._session.commit()
            raise _INVALID_REFRESH_TOKEN

        if stored.expires_at <= utcnow_naive():
            raise _INVALID_REFRESH_TOKEN

        user = await self._users.get_by_id(stored.user_id)
        if user is None:
            raise _INVALID_REFRESH_TOKEN

        # 토큰 로테이션: 사용된 refresh token은 즉시 폐기하고 새 쌍을 발급한다.
        # 위에서 "아직 안 폐기됨"을 확인한 것과 실제로 폐기하는 것 사이에도 시간차가
        # 있는 check-then-act다 - 같은 토큰으로 거의 동시에 온 다른 요청도 같은 확인을
        # 통과해 있을 수 있어서, 일반 UPDATE로 그냥 폐기하면 둘 다 성공해 하나의 토큰
        # 소비로 두 개의 유효한 세션이 나온다(로테이션/재사용 탐지가 막으려던 상황
        # 그대로 허용). revoke_if_active는 `WHERE revoked_at IS NULL`을 건 원자적
        # UPDATE라 그 중 하나만 실제로 성공한다 - 실패한 쪽은 이미 재사용된(=탈취
        # 의심) 토큰을 만난 것과 동일하게 취급해 전체 세션을 강제로 끊는다.
        if not await self._refresh_tokens.revoke_if_active(stored.id):
            await self._refresh_tokens.revoke_all_for_user(stored.user_id)
            await self._session.commit()
            raise _INVALID_REFRESH_TOKEN

        # get_by_id 확인과 여기 사이에 다른 요청이 UserService.delete_account()로
        # 이 계정을 지워버리면(login()과 같은 이유 - RefreshToken.user_id는
        # nullable=False FK), _issue_tokens()의 INSERT가 IntegrityError로 실패한다.
        # 잡지 않으면 처리되지 않은 예외(500)로 새어나간다 - 위 revoke_if_active()
        # 성공(UPDATE)도 아직 커밋 전이라, 여기서 rollback()하면 그 폐기까지 함께
        # 되돌아가 낡은 refresh_token을 헛되이 태우지 않는다.
        try:
            tokens = await self._issue_tokens(user)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise _INVALID_REFRESH_TOKEN from None
        return tokens

    async def create_guest_session(self) -> TokenResponse:
        """로그인 폼 없이 방문자마다 자동으로 익명 계정을 만들고 토큰을 발급한다.

        이 토큰/refresh_token을 클라이언트가 잃어버리면(로그아웃, 스토리지 삭제 등)
        해당 게스트 계정의 데이터는 다시 접근할 방법이 없다 - 전환 전까지는 별도의
        이메일/비밀번호가 없기 때문이다. 실제 계정으로 전환하려면
        UserService.upgrade_guest()(POST /users/me/upgrade)를 쓰면 된다.
        """
        user = await self._users.create_guest()
        tokens = await self._issue_tokens(user)
        await self._session.commit()
        return tokens

    async def logout(self, refresh_token: str) -> None:
        token_hash = hash_refresh_token(refresh_token)
        stored = await self._refresh_tokens.get_by_hash(token_hash)
        if stored is not None and stored.revoked_at is None:
            await self._refresh_tokens.revoke(stored)
        await self._session.commit()

    async def list_active_sessions(
        self, user_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[list[RefreshToken], int]:
        """현재 로그인 상태인(폐기되지 않고 만료되지 않은) refresh token 목록을
        "세션"으로 노출한다. 이 API는 access token으로 인증하므로, 지금 요청을
        보내는 클라이언트 자신이 어느 세션에 해당하는지는 알 수 없다 - RefreshToken이
        발급 당시의 access token과 연결되어 있지 않기 때문이다. 그래도 활성 세션
        개수 확인과 특정/전체 세션 강제 로그아웃에는 충분히 유용하다."""
        sessions = await self._refresh_tokens.list_active_for_user(user_id, limit=limit, offset=offset)
        total = await self._refresh_tokens.count_active_for_user(user_id)
        return sessions, total

    async def revoke_session(self, user_id: uuid.UUID, session_id: uuid.UUID) -> None:
        token = await self._refresh_tokens.get_active_by_id_for_user(session_id, user_id)
        if token is None:
            raise _SESSION_NOT_FOUND
        # get_active_by_id_for_user()는 잠금 없는 조회라, 그 조회와 아래 revoke()의
        # UPDATE 사이에 다른 요청이 DELETE /users/me로 이 계정을 지워버리면(FK가
        # ON DELETE CASCADE라 refresh_tokens 행도 함께 사라짐) 이 UPDATE가 0행에
        # 매치돼 StaleDataError가 난다 - study_service.py 등의 rename_session()이
        # 겪던 것과 같은 종류의 경쟁(185라운드)을 이 테이블에서도 겪는다.
        # revoke_all_sessions()는 WHERE 절을 건 Core 벌크 UPDATE라 이 문제가 없다.
        try:
            await self._refresh_tokens.revoke(token)
            await self._session.commit()
        except StaleDataError:
            await self._session.rollback()
            raise _SESSION_NOT_FOUND from None

    async def revoke_all_sessions(self, user_id: uuid.UUID) -> None:
        await self._refresh_tokens.revoke_all_for_user(user_id)
        await self._session.commit()

    async def _issue_tokens(self, user: User) -> TokenResponse:
        access_token = create_access_token(user.id, self._settings)
        raw_refresh_token = generate_refresh_token()
        await self._refresh_tokens.create(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh_token),
            expires_at=refresh_token_expiry(self._settings),
        )
        return TokenResponse(access_token=access_token, refresh_token=raw_refresh_token)
