from functools import lru_cache

import bcrypt

# bcrypt는 72바이트를 넘는 입력을 조용히 잘라버리므로, 그보다 긴 비밀번호는 명시적으로 거부한다.
_MAX_PASSWORD_BYTES = 72


class PasswordTooLongError(ValueError):
    pass


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > _MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(f"비밀번호는 최대 {_MAX_PASSWORD_BYTES}바이트까지 허용됩니다.")
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """존재하지 않는 사용자로 로그인 시도할 때도 실제 사용자가 있을 때와 똑같이
    bcrypt 비교 한 번을 수행하기 위한, 누구의 비밀번호도 아닌 고정 해시.
    이게 없으면 "이메일 조회 실패 시 즉시 반환 vs 존재하면 bcrypt까지 수행"의
    응답 시간 차이로 공격자가 어떤 이메일이 가입돼 있는지 추측할 수 있다
    (타이밍 기반 계정 존재 여부 유출). 최초 호출 시 한 번만 계산해 캐싱한다.
    """
    return hash_password("no-such-account-timing-attack-mitigation-dummy")


def verify_password(password: str, hashed_password: str | None) -> bool:
    """hashed_password가 None이면(이메일이 존재하지 않거나 게스트 계정) 더미
    해시와 비교해서 항상 같은 bcrypt 비용을 지불하게 한다 - 호출부는 반환값과
    무관하게 이 함수를 매번 호출해야 타이밍 방어 효과가 있다(단축 평가로
    건너뛰면 안 됨).

    `hash_password()`는 72바이트를 넘는 입력을 명시적으로 거부하지만, 이 함수는
    그 가드가 없었다 - `bcrypt.checkpw()`도 72바이트를 넘으면 조용히 자르는 대신
    `ValueError`를 던지는데, 로그인(`LoginRequest.password`의 `max_length=72`는
    "문자 수" 기준이라 멀티바이트 문자를 쓰면 통과하고도 바이트 수는 넘을 수
    있음)이나 `current_password`류 필드(애초에 길이 제한이 아예 없음)를 통해
    이 예외가 그대로 새어나가 처리되지 않은 500이 될 수 있었다. 72바이트를
    넘는 입력은 어차피 실제 비밀번호와 일치할 수 없으므로(그런 긴 비밀번호는
    애초에 해시로 저장될 수 없었다) 예외를 전파하는 대신 안전하게 "일치하지
    않음"으로 처리한다 - 이 조기 반환은 제출된 비밀번호의 길이(공격자가 이미
    아는 값)에만 의존하고 `hashed_password`/계정 존재 여부와는 무관하므로,
    위에서 막으려는 타이밍 기반 계정 존재 여부 유출과는 다른 성격이라 안전하다."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > _MAX_PASSWORD_BYTES:
        return False
    if hashed_password is None:
        hashed_password = _dummy_hash()
    return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
