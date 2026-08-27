import asyncio
import json
import logging
import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import (
    get_current_user,
    get_current_user_ws,
    get_ollama_service,
    get_rag_service,
    limit_ws_connections,
)
from app.core.rate_limit import check_rate_limit, limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.study import (
    StudyMessageCreateRequest,
    StudyMessageCreateResponse,
    StudyMessageResponse,
    StudySessionCreateRequest,
    StudySessionDetailResponse,
    StudySessionResponse,
    StudySessionUpdateRequest,
)
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService
from app.services.study_service import StudyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/study/sessions", tags=["study"])


def get_study_service(
    session: AsyncSession = Depends(get_db),
    ollama_service: OllamaService = Depends(get_ollama_service),
    rag_service: RagService = Depends(get_rag_service),
    settings: Settings = Depends(get_settings),
) -> StudyService:
    return StudyService(
        session=session, ollama_service=ollama_service, rag_service=rag_service, settings=settings
    )


@router.post("", response_model=StudySessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: StudySessionCreateRequest,
    current_user: User = Depends(get_current_user),
    study_service: StudyService = Depends(get_study_service),
) -> StudySessionResponse:
    study_session = await study_service.create_session(
        user_id=current_user.id, title=payload.title, model=payload.model
    )
    return StudySessionResponse.model_validate(study_session)


@router.get("", response_model=list[StudySessionResponse])
async def list_sessions(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    study_service: StudyService = Depends(get_study_service),
) -> list[StudySessionResponse]:
    sessions, total = await study_service.list_sessions(
        user_id=current_user.id, limit=limit, offset=offset
    )
    response.headers["X-Total-Count"] = str(total)
    return [StudySessionResponse.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=StudySessionDetailResponse)
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    study_service: StudyService = Depends(get_study_service),
) -> StudySessionDetailResponse:
    study_session, messages = await study_service.get_session_with_messages(
        session_id=session_id, user_id=current_user.id
    )
    return StudySessionDetailResponse(
        id=study_session.id,
        title=study_session.title,
        model=study_session.model,
        created_at=study_session.created_at,
        updated_at=study_session.updated_at,
        messages=[StudyMessageResponse.model_validate(m) for m in messages],
    )


@router.patch("/{session_id}", response_model=StudySessionResponse)
async def rename_session(
    session_id: uuid.UUID,
    payload: StudySessionUpdateRequest,
    current_user: User = Depends(get_current_user),
    study_service: StudyService = Depends(get_study_service),
) -> StudySessionResponse:
    study_session = await study_service.rename_session(
        session_id=session_id, user_id=current_user.id, title=payload.title
    )
    return StudySessionResponse.model_validate(study_session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    study_service: StudyService = Depends(get_study_service),
) -> None:
    await study_service.delete_session(session_id=session_id, user_id=current_user.id)


@router.post("/{session_id}/messages", response_model=StudyMessageCreateResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def send_message(
    request: Request,
    response: Response,
    session_id: uuid.UUID,
    payload: StudyMessageCreateRequest,
    current_user: User = Depends(get_current_user),
    study_service: StudyService = Depends(get_study_service),
) -> StudyMessageCreateResponse:
    user_message, assistant_message = await study_service.send_message(
        session_id=session_id, user_id=current_user.id, content=payload.content
    )
    return StudyMessageCreateResponse(
        user_message=StudyMessageResponse.model_validate(user_message),
        assistant_message=StudyMessageResponse.model_validate(assistant_message),
    )


@router.websocket("/{session_id}/stream")
async def stream_message(
    websocket: WebSocket,
    session_id: uuid.UUID,
    _connection_slot: None = Depends(limit_ws_connections),
    current_user: User = Depends(get_current_user_ws),
    study_service: StudyService = Depends(get_study_service),
) -> None:
    """send_message의 스트리밍 버전. 인증은 쿼리 파라미터(?token=...)로 받는다 -
    브라우저 WebSocket API가 커스텀 헤더를 지원하지 않기 때문이다.

    클라이언트가 {"content": "..."}를 보내면, 서버는 순서대로
    {"type": "user_message", "data": {...}} → {"type": "delta", "content": "..."}*
    → {"type": "done", "data": {...}} 를 보낸다. 실패하면 {"type": "error", "detail": "..."}.

    기존 REST 엔드포인트(POST /{session_id}/messages)는 그대로 남겨둔다 - 이건
    완전히 별도 경로라 하위호환을 깨지 않는다. slowapi의 @limiter.limit() 데코레이터는
    HTTP 요청/응답 사이클 전용이라 이 WebSocket 경로에는 못 붙이므로, 같은 storage를
    공유하는 core.rate_limit.check_rate_limit()로 메시지 하나하나마다 수동으로
    확인한다 (REST 엔드포인트와는 별도 버킷 - IP당 chat_rate_limit을 이 경로에도
    독립적으로 적용).

    클라이언트가 ws_idle_timeout_seconds(기본 5분) 동안 메시지를 하나도 안 보내면
    연결을 끊는다 - 이 연결이 붙잡고 있는 DB 커넥션/Ollama 클라이언트를 방치된
    연결이 무한정 점유해 커넥션 풀을 고갈시키는 것을 막기 위함이다.

    방치된 연결뿐 아니라 활발하게 메시지를 주고받는 연결도(면접복기 스트리밍과
    합쳐) max_concurrent_ws_connections(기본 6)개보다 많이 동시에 열리면 같은
    이유로 DB 커넥션 풀을 고갈시킬 수 있다 - limit_ws_connections 의존성이
    accept() 전에 상한을 확인해, 넘으면 연결 자체를 거부한다.
    """
    await websocket.accept()
    settings = get_settings()
    max_length = settings.max_prompt_length
    client_ip = websocket.client.host if websocket.client else "127.0.0.1"
    try:
        while True:
            try:
                payload = await asyncio.wait_for(
                    websocket.receive_json(), timeout=settings.ws_idle_timeout_seconds
                )
            except asyncio.TimeoutError:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE, reason="idle timeout")
                break
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "잘못된 JSON 형식입니다."})
                continue
            if not isinstance(payload, dict):
                await websocket.send_json({"type": "error", "detail": "잘못된 요청 형식입니다."})
                continue
            content = payload.get("content")
            if not isinstance(content, str) or not content.strip():
                await websocket.send_json({"type": "error", "detail": "content는 비어 있을 수 없습니다."})
                continue
            if len(content) > max_length:
                await websocket.send_json(
                    {"type": "error", "detail": f"메시지는 최대 {max_length}자까지 허용됩니다."}
                )
                continue

            allowed, retry_after = check_rate_limit(
                f"ws:study:{client_ip}", get_settings().chat_rate_limit
            )
            if not allowed:
                await websocket.send_json(
                    {
                        "type": "error",
                        "detail": "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
                        "retry_after": retry_after,
                    }
                )
                continue

            try:
                async for event_type, data in study_service.stream_message(
                    session_id=session_id, user_id=current_user.id, content=content
                ):
                    if event_type == "delta":
                        await websocket.send_json({"type": "delta", "content": data})
                    elif event_type == "user_message":
                        await websocket.send_json(
                            {
                                "type": "user_message",
                                "data": StudyMessageResponse.model_validate(data).model_dump(mode="json"),
                            }
                        )
                    elif event_type == "assistant_message":
                        await websocket.send_json(
                            {
                                "type": "done",
                                "data": StudyMessageResponse.model_validate(data).model_dump(mode="json"),
                            }
                        )
            except HTTPException as exc:
                await websocket.send_json({"type": "error", "detail": exc.detail})
            except Exception:
                # main.py의 전역 unhandled_exception_handler(app.exception_handler(Exception))는
                # Starlette의 ServerErrorMiddleware에만 걸리는데, 이 미들웨어는 websocket
                # scope에서는 그대로 통과시키기만 하고 아무 일도 하지 않는다 - 즉 HTTPException이
                # 아닌 예외(DB 커넥션 끊김, 예상 못 한 임베딩/RAG 오류 등)는 이 라우트에서 직접
                # 잡지 않으면 로그 한 줄 없이, 클라이언트에게 에러 이벤트도 못 보낸 채 연결만
                # 뚝 끊긴다. 트랜잭션 상태가 이미 깨졌을 수 있어(부분 flush 도중 실패) 세션을
                # 계속 재사용하지 않고 연결을 닫는다.
                logger.exception("스트리밍 중 처리되지 않은 예외 발생: session_id=%s", session_id)
                await websocket.send_json({"type": "error", "detail": "메시지 처리 중 오류가 발생했습니다."})
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                return
    except WebSocketDisconnect:
        pass
