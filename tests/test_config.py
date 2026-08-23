import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_accepts_sufficiently_long_jwt_secret_key():
    settings = Settings(jwt_secret_key="a" * 32)
    assert settings.jwt_secret_key == "a" * 32


def test_settings_rejects_jwt_secret_key_shorter_than_minimum():
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="too-short")
    assert "JWT_SECRET_KEY는 최소 32자 이상이어야 합니다" in str(exc_info.value)


def test_settings_rejects_empty_jwt_secret_key():
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key="")


def test_settings_normalizes_lowercase_log_level():
    """logging.basicConfig(level=...)는 소문자("info")를 받아들이지 않고
    create_app()이 호출될 때마다 ValueError로 앱을 죽인다 - 설정 로딩
    시점에 대문자로 정규화해서 이 문제를 근본적으로 막는다."""
    settings = Settings(jwt_secret_key="a" * 32, log_level="info")
    assert settings.log_level == "INFO"


def test_settings_rejects_invalid_log_level():
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="a" * 32, log_level="INOF")
    assert "LOG_LEVEL은" in str(exc_info.value)
