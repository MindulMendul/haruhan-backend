import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.core.clock import utcnow_naive
from app.core.config import Settings

ACCESS_TOKEN_TYPE = "access"


def create_access_token(user_id: uuid.UUID, settings: Settings) -> str:
    # exp/iat는 정수 epoch초로 넘긴다. naive datetime을 그대로 넘기면 PyJWT가
    # 서버 로컬 타임존 기준으로 해석해버려 UTC가 아닌 서버에서 만료 시각이 틀어질 수 있다.
    now_ts = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": now_ts,
        "exp": now_ts + settings.access_token_expire_minutes * 60,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict:
    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("Unexpected token type")
    return payload


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry(settings: Settings) -> datetime:
    return utcnow_naive() + timedelta(days=settings.refresh_token_expire_days)
