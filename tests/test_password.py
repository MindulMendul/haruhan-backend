import pytest

from app.core.password import PasswordTooLongError, hash_password, verify_password


def test_hash_and_verify_round_trip():
    hashed = hash_password("supersecret")
    assert verify_password("supersecret", hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_hash_password_rejects_over_byte_limit():
    with pytest.raises(PasswordTooLongError):
        hash_password("가" * 72)  # 72자지만 UTF-8로는 72바이트를 넘음


def test_verify_password_with_none_hash_returns_false():
    """존재하지 않는 사용자/게스트 계정처럼 대조할 해시가 없는 경우, 더미 해시와
    비교해서 항상 False를 반환해야 한다(그리고 예외 없이 정상적으로 bcrypt 비교
    자체는 수행되어야 한다 - 그래야 실제 사용자가 있을 때와 응답 시간이 비슷해져
    타이밍 공격을 막을 수 있다)."""
    assert verify_password("아무 비밀번호", None) is False


def test_verify_password_with_none_hash_is_consistent_across_calls():
    # 매번 새로 해시를 계산하는 게 아니라 캐싱된 더미 해시를 재사용하는지 확인 -
    # 여러 번 호출해도 안정적으로 같은 결과를 내야 한다.
    for _ in range(5):
        assert verify_password("random-guess", None) is False


def test_verify_password_rejects_password_over_byte_limit():
    """hash_password()와 달리 verify_password()는 72바이트를 넘는 입력에 대한
    가드가 없었다 - bcrypt.checkpw()가 조용히 자르는 대신 ValueError를 던지는데,
    이게 로그인/current_password 검증 경로에서 처리되지 않은 500으로 새어나갔다.
    72바이트를 넘는 입력은 어차피 실제 비밀번호와 일치할 수 없으므로, 예외 대신
    안전하게 False를 반환해야 한다."""
    hashed = hash_password("supersecret")
    assert verify_password("가" * 72, hashed) is False  # 72자지만 UTF-8로는 72바이트를 넘음


def test_verify_password_rejects_password_over_byte_limit_with_none_hash():
    # hashed_password가 None인 경로(더미 해시 비교)에서도 같은 가드가 적용되는지 확인.
    assert verify_password("가" * 72, None) is False
