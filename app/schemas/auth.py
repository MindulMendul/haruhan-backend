import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.validators import NormalizedEmail, UtcDatetime


class SignupRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(..., min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(..., min_length=1, max_length=72)


class RefreshRequest(BaseModel):
    # 실제 발급되는 값(core.tokens.generate_refresh_token, secrets.token_urlsafe(32))은
    # 43자 고정이지만, 다른 사용자 입력 필드(password, chat/review content, title 등)와
    # 마찬가지로 명시적 상한을 둔다 - 인증 전(=/auth/refresh, /auth/logout 둘 다 로그인
    # 없이 호출됨)에 처리되는 필드라 여유 있게 잡아둔 안전장치.
    refresh_token: str = Field(..., min_length=1, max_length=512)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: UtcDatetime
    expires_at: UtcDatetime
