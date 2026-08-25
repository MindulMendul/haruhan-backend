import asyncio
import uuid
from collections.abc import AsyncIterator

import jwt
from fastapi import Depends, HTTPException, WebSocket, WebSocketException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.tokens import decode_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.user_repository import UserRepository
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService

_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail={"code": "invalid_token", "message": "Could not validate credentials"},
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


async def get_current_user_ws(
    websocket: WebSocket,
    session: AsyncSession = Depends(get_db),
) -> User:
    """WebSocket용 인증. 브라우저 WebSocket API는 커스텀 헤더를 못 보내므로
    Authorization 헤더 대신 쿼리 파라미터(?token=<access_token>)로 받는다."""
    settings = get_settings()
    token = websocket.query_params.get("token")
    if token is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    try:
        payload = decode_access_token(token, settings)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION) from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    return user


_active_ws_connections = 0
_ws_connections_lock = asyncio.Lock()


def reset_ws_connection_counter() -> None:
    """테스트 간 상태를 격리하기 위한 초기화용 - 이전 테스트의 연결이 비정상
    종료로 finally를 못 거치고 카운터를 남겼을 가능성에 대비한다."""
    global _active_ws_connections
    _active_ws_connections = 0


async def limit_ws_connections(settings: Settings = Depends(get_settings)) -> AsyncIterator[None]:
    """동시 WebSocket 연결 수를 상한(max_concurrent_ws_connections) 아래로 제한한다.

    WebSocket 연결 하나는 accept부터 종료까지 get_db()가 물어다 주는 DB 커넥션
    풀의 커넥션 하나를 계속 점유한다(메시지 하나 처리할 때만 잠깐 빌리는 게
    아니라 study_service/rag_service를 만드는 Depends(get_db)가 연결 전체
    수명 동안 열려 있는 yield 의존성이기 때문) - 풀 크기(기본
    pool_size=5 + max_overflow=5 = 10)보다 많은 동시 연결이 열리면 풀 전체가
    고갈돼 이 WebSocket 라우트뿐 아니라 앱의 다른 모든 HTTP/WebSocket 요청까지
    막힌다. accept() 전에(다른 의존성보다 먼저 선언해서) 이 의존성이 실행되므로,
    상한을 넘으면 연결을 아예 받지 않고 깨끗하게 거부한다 - DB 커넥션을 실제로
    쓸 일 없이 곧바로 종료된다.
    """
    global _active_ws_connections
    async with _ws_connections_lock:
        if _active_ws_connections >= settings.max_concurrent_ws_connections:
            raise WebSocketException(code=status.WS_1013_TRY_AGAIN_LATER)
        _active_ws_connections += 1
    try:
        yield
    finally:
        async with _ws_connections_lock:
            _active_ws_connections -= 1


async def get_ollama_service(settings: Settings = Depends(get_settings)) -> AsyncIterator[OllamaService]:
    """요청(HTTP 하나 또는 WebSocket 연결 하나) 동안 재사용할 OllamaService를
    만든다. OllamaService는 내부적으로 httpx.AsyncClient 하나를 계속 재사용해
    커넥션을 유지하므로, 요청/연결이 끝나면 반드시 닫아줘야 한다 - yield 이후의
    코드가 FastAPI에 의해 정리(cleanup) 시점에 실행된다."""
    service = OllamaService(base_url=settings.ollama_base_url)
    try:
        yield service
    finally:
        await service.aclose()


def get_rag_service(
    session: AsyncSession = Depends(get_db),
    ollama_service: OllamaService = Depends(get_ollama_service),
    settings: Settings = Depends(get_settings),
) -> RagService:
    return RagService(session=session, ollama_service=ollama_service, settings=settings)
