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


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
