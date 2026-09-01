import unicodedata
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, EmailStr, PlainSerializer


def _normalize_email(value: str) -> str:
    return value.strip().lower()


# 이메일 대소문자를 서비스 전체 입력 경계(회원가입/로그인/게스트 승격/프로필 수정)에서
# 하나로 통일한다. User.email의 unique 제약은 원본 대소문자 그대로를 비교하므로,
# 정규화 없이는 "User@Example.com"과 "user@example.com"이 서로 다른 계정으로
# 등록/로그인되어 같은 메일함 소유자가 의도치 않게 중복 계정을 만들 수 있었다.
NormalizedEmail = Annotated[EmailStr, AfterValidator(_normalize_email)]


# 한글 채움 문자(초성/중성 채움, 반각 포함) - 유니코드 Lo("기타 문자") 카테고리라
# str.isspace()도 False, unicodedata.category() == "Cf"도 아니어서 아래 is_blank()의
# 기존 두 조건 중 어느 것도 못 잡는다. 그런데도 한글 지원 폰트에서는 전부 아무것도
# 안 보이는 빈칸으로 렌더링되고, 특히 U+3164(HANGUL FILLER)는 한글 채팅/게임
# 플랫폼에서 "안 보이는 닉네임/메시지"를 만드는 데 실제로 흔히 쓰이는 문자다 -
# 이 앱이 한국어 서비스인 만큼 실제로 마주칠 가능성이 낮지 않다.
_HANGUL_FILLER_CHARS = frozenset(
    "ᅟ"  # HANGUL CHOSEONG FILLER
    "ᅠ"  # HANGUL JUNGSEONG FILLER
    "ㅤ"  # HANGUL FILLER
    "ﾠ"  # HALFWIDTH HANGUL FILLER
)


def is_blank(value: str) -> bool:
    """문자열 전체가 공백이거나 유니코드 Cf("서식") 카테고리 문자, 또는 한글 채움
    문자뿐인지 확인한다.

    `str.strip()`은 `str.isspace()`가 True인 문자(공백류)만 제거하고, 폭 없는
    문자(zero-width space U+200B, ZWNJ/ZWJ, word joiner U+2060, BOM U+FEFF 등
    유니코드 Cf 카테고리)는 공백이 아니라고 보아 그대로 남긴다 - 그 결과
    `"​​"` 같은, 화면에는 아무것도 안 보이는 문자열이
    `not value.strip()` 검사를 통과해버린다(공백류 문자가 하나도 없어 strip이
    아무것도 제거하지 못함). 이 문자들만으로 이루어진 값도 공백류와 똑같이
    "실질적으로 비어있음"으로 취급한다.

    한글 채움 문자(_HANGUL_FILLER_CHARS)는 Cf가 아니라 Lo("기타 문자")
    카테고리라 위 두 조건 중 어느 쪽에도 안 걸려, `is_blank("ㅤㅤㅤ")`가
    (한글 지원 폰트에서는 완전히 빈 칸으로 보이는데도) False를 반환하던 것을
    실제로 확인했다 - 학습챗/퀴즈/면접연습/면접복기의 제목·주제·회사명·
    직무명 같은 라벨 필드(NonBlankStr)에 넣으면 목록에서 빈 줄처럼 보이는
    항목을 그대로 만들 수 있고, content/prompt/answer 필드에 넣으면 사용자가
    보기엔 빈 입력인데도 검증을 통과해 AI 호출이 낭비되거나(면접연습 답변은
    한 번만 기록되는 CAS라 재제출 방법도 없음) 한다."""
    return all(
        ch.isspace() or unicodedata.category(ch) == "Cf" or ch in _HANGUL_FILLER_CHARS
        for ch in value
    )


def _reject_blank(value: str) -> str:
    if is_blank(value):
        raise ValueError("공백만 입력할 수 없습니다.")
    return value


# min_length=1은 "" 만 막을 뿐 "   " 같은 공백-only 값은 그대로 통과시킨다.
# 학습챗/퀴즈/면접연습/면접복기 목록에서 제목·주제·회사명·직무명처럼 사용자에게
# 그대로 노출되는 라벨 필드에 공백-only 값이 들어가면 목록에 빈 줄처럼 보이는
# 항목이 생겨 다른 항목과 구별할 수 없게 된다.
NonBlankStr = Annotated[str, AfterValidator(_reject_blank)]


def _serialize_as_utc(value: datetime) -> str:
    # core.clock.utcnow_naive()로 DB에는 항상 tz 정보 없는 UTC datetime만 저장하므로,
    # 이 타입을 쓰는 응답 필드는 전부 naive UTC 값만 받는다. Pydantic 기본
    # datetime.isoformat() 직렬화는 naive 값에 "Z"/오프셋을 붙이지 않는데,
    # JS의 `new Date("...")`는 그 문자열에 타임존 표기가 없으면 UTC가 아니라
    # 브라우저 로컬 시간으로 해석한다(ECMA-262) - 그 결과 프론트가 자연스럽게
    # 표시하면 모든 타임스탬프가 브라우저의 UTC 오프셋만큼 틀어져 보인다.
    # docs/FRONTEND_INTEGRATION.md도 이 필드들을 "Z" 접미사가 붙은 형태로 문서화하고
    # 있어(예: submitted_at), 실제 응답도 그 문서와 일치하도록 명시적으로 맞춘다.
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.isoformat()


# API 응답에 노출되는 datetime 필드 전용 - 항상 UTC를 나타내는 "Z" 접미사를 붙여
# 직렬화한다. 요청(request) 스키마의 datetime 필드에는 쓰지 않는다(이 앱은 datetime
# 입력을 받는 요청 필드가 없다).
UtcDatetime = Annotated[datetime, PlainSerializer(_serialize_as_utc, return_type=str)]
