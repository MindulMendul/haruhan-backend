import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.tokens import decode_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.services.ollama_service import OllamaService

_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise _CREDENTIALS_ERROR

    settings = get_settings()
    try:
        payload = decode_access_token(credentials.credentials, settings)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise _CREDENTIALS_ERROR from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise _CREDENTIALS_ERROR
    return user


def get_ollama_service(settings: Settings = Depends(get_settings)) -> OllamaService:
    return OllamaService(base_url=settings.ollama_base_url)
