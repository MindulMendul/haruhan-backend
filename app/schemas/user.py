import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    # email/password 변경은 탈취된 access token만으로 계정을 완전히 뺏기지 못하도록
    # 반드시 현재 비밀번호 확인을 요구한다.
    current_password: str | None = None

    @model_validator(mode="after")
    def _require_current_password_when_changing_credentials(self) -> "UserUpdateRequest":
        if (self.email is not None or self.password is not None) and not self.current_password:
            raise ValueError("email 또는 password를 변경하려면 current_password가 필요합니다.")
        return self
