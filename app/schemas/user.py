import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, model_validator

from app.schemas.validators import NormalizedEmail


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]  # pydantic v2 computed_field + property, mypy plugin gap
    @property
    def is_guest(self) -> bool:
        return self.email is None


class GuestUpgradeRequest(BaseModel):
    """게스트 계정에 email/password를 등록해 실계정으로 승격시킬 때 쓴다.

    게스트는 hashed_password가 없어(=대조할 기존 비밀번호가 없어) current_password를
    요구하지 않는다. 이미 실계정인 사용자가 호출하면 서비스 계층에서 409로 거부한다.
    """

    email: NormalizedEmail
    password: str = Field(min_length=8, max_length=72)


class AccountDeletionRequest(BaseModel):
    """계정과 연관 데이터 전체를 영구 삭제할 때 쓴다. 실계정은 탈취된 access
    token만으로 계정을 통째로 지우지 못하도록 현재 비밀번호로 재확인해야 하고,
    게스트 계정은 비교할 비밀번호가 없으므로 생략 가능하다."""

    current_password: str | None = None


class UserUpdateRequest(BaseModel):
    email: NormalizedEmail | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    # email/password 변경은 탈취된 access token만으로 계정을 완전히 뺏기지 못하도록
    # 반드시 현재 비밀번호 확인을 요구한다.
    current_password: str | None = None

    @model_validator(mode="after")
    def _require_current_password_when_changing_credentials(self) -> "UserUpdateRequest":
        if (self.email is not None or self.password is not None) and not self.current_password:
            raise ValueError("email 또는 password를 변경하려면 current_password가 필요합니다.")
        return self
