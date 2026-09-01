import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.core.tokens import (
    ACCESS_TOKEN_TYPE,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
)


def test_create_and_decode_access_token_round_trip():
    settings = get_settings()
    user_id = uuid.uuid4()

    token = create_access_token(user_id, settings)
    payload = decode_access_token(token, settings)

    assert payload["sub"] == str(user_id)
    assert payload["type"] == ACCESS_TOKEN_TYPE


def test_decode_access_token_rejects_wrong_token_type():
    # 리프레시 토큰은 JWT가 아니라 불투명한 랜덤 문자열이라 이 분기가 API를 통해
    # 자연스럽게 트리거될 일은 없다 - 미래에 다른 종류의 JWT가 추가되거나, 서명
    # 위조 없이 타입만 조작된 토큰이 들어오는 것을 막는 방어선이라 직접 조작한
    # 토큰으로 단위 테스트한다.
    settings = get_settings()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": "refresh", "iat": now_ts, "exp": now_ts + 60},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(forged, settings)


def test_decode_access_token_rejects_expired_token():
    settings = get_settings()
    now_ts = int(datetime.now(timezone.utc).timestamp())
    expired = jwt.encode(
        {"sub": str(uuid.uuid4()), "type": ACCESS_TOKEN_TYPE, "iat": now_ts - 120, "exp": now_ts - 60},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired, settings)


def test_decode_access_token_rejects_wrong_secret():
    settings = get_settings()
    token = create_access_token(uuid.uuid4(), settings)

    class _WrongSecretSettings:
        jwt_secret_key = "different-secret"
        jwt_algorithm = settings.jwt_algorithm

    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token, _WrongSecretSettings())


def test_generate_refresh_token_produces_distinct_values():
    tokens = {generate_refresh_token() for _ in range(20)}
    assert len(tokens) == 20


def test_hash_refresh_token_is_deterministic_and_matches_sha256():
    token = "some-refresh-token"
    import hashlib

    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert hash_refresh_token(token) == hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_refresh_token_expiry_is_days_from_now():
    settings = get_settings()
    from app.core.clock import utcnow_naive

    before = utcnow_naive()
    expiry = refresh_token_expiry(settings)
    after = utcnow_naive()

    expected_min = before + timedelta(days=settings.refresh_token_expire_days)
    expected_max = after + timedelta(days=settings.refresh_token_expire_days)
    assert expected_min <= expiry <= expected_max
