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
    건너뛰면 안 됨)."""
    if hashed_password is None:
        hashed_password = _dummy_hash()
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
