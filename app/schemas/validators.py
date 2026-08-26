from typing import Annotated

from pydantic import AfterValidator, EmailStr


def _normalize_email(value: str) -> str:
    return value.strip().lower()


# 이메일 대소문자를 서비스 전체 입력 경계(회원가입/로그인/게스트 승격/프로필 수정)에서
# 하나로 통일한다. User.email의 unique 제약은 원본 대소문자 그대로를 비교하므로,
# 정규화 없이는 "User@Example.com"과 "user@example.com"이 서로 다른 계정으로
# 등록/로그인되어 같은 메일함 소유자가 의도치 않게 중복 계정을 만들 수 있었다.
NormalizedEmail = Annotated[EmailStr, AfterValidator(_normalize_email)]


def _reject_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("공백만 입력할 수 없습니다.")
    return value


# min_length=1은 "" 만 막을 뿐 "   " 같은 공백-only 값은 그대로 통과시킨다.
# 학습챗/퀴즈/면접연습/면접복기 목록에서 제목·주제·회사명·직무명처럼 사용자에게
# 그대로 노출되는 라벨 필드에 공백-only 값이 들어가면 목록에 빈 줄처럼 보이는
# 항목이 생겨 다른 항목과 구별할 수 없게 된다.
NonBlankStr = Annotated[str, AfterValidator(_reject_blank)]
