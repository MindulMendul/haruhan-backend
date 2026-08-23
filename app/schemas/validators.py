from typing import Annotated

from pydantic import AfterValidator, EmailStr


def _normalize_email(value: str) -> str:
    return value.strip().lower()


# 이메일 대소문자를 서비스 전체 입력 경계(회원가입/로그인/게스트 승격/프로필 수정)에서
# 하나로 통일한다. User.email의 unique 제약은 원본 대소문자 그대로를 비교하므로,
# 정규화 없이는 "User@Example.com"과 "user@example.com"이 서로 다른 계정으로
# 등록/로그인되어 같은 메일함 소유자가 의도치 않게 중복 계정을 만들 수 있었다.
NormalizedEmail = Annotated[EmailStr, AfterValidator(_normalize_email)]
