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

from app.core.config import get_settings
from app.core.dependencies import (
    get_current_user,
    get_current_user_ws,
    get_ollama_service,
    get_rag_service,
)
from app.core.rate_limit import limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.study import (
    StudyMessageCreateRequest,
    StudyMessageCreateResponse,
    StudyMessageResponse,
    StudySessionCreateRequest,
    StudySessionDetailResponse,
    StudySessionResponse,
)
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService
from app.services.study_service import StudyService

router = APIRouter(prefix="/study/sessions", tags=["study"])


def get_study_service(
    session: AsyncSession = Depends(get_db),
    ollama_service: OllamaService = Depends(get_ollama_service),
    rag_service: RagService = Depends(get_rag_service),
) -> StudyService:
    return StudyService(session=session, ollama_service=ollama_service, rag_service=rag_service)


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
    current_user: User = Depends(get_current_user_ws),
    study_service: StudyService = Depends(get_study_service),
) -> None:
    """send_message의 스트리밍 버전. 인증은 쿼리 파라미터(?token=...)로 받는다 -
    브라우저 WebSocket API가 커스텀 헤더를 지원하지 않기 때문이다.

    클라이언트가 {"content": "..."}를 보내면, 서버는 순서대로
    {"type": "user_message", "data": {...}} → {"type": "delta", "content": "..."}*
    → {"type": "done", "data": {...}} 를 보낸다. 실패하면 {"type": "error", "detail": "..."}.

    기존 REST 엔드포인트(POST /{session_id}/messages)는 그대로 남겨둔다 - 이건
    완전히 별도 경로라 하위호환을 깨지 않는다. slowapi의 레이트리밋 데코레이터는
    HTTP 라우트 전용이라 이 WebSocket 경로에는 아직 적용되어 있지 않다(후속 과제).
    """
    await websocket.accept()
    max_length = get_settings().max_prompt_length
    try:
        while True:
            payload = await websocket.receive_json()
            content = payload.get("content")
            if not isinstance(content, str) or not content.strip():
                await websocket.send_json({"type": "error", "detail": "content는 비어 있을 수 없습니다."})
                continue
            if len(content) > max_length:
                await websocket.send_json(
                    {"type": "error", "detail": f"메시지는 최대 {max_length}자까지 허용됩니다."}
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
    except WebSocketDisconnect:
        pass
