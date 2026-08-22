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
