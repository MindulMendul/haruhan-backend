import asyncio
import json
import logging
import time
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
    is_ws_token_expired,
    limit_ws_connections,
)
from app.core.middleware import access_logger
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
from app.schemas.validators import is_blank
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

    AccessLogMiddleware(core/middleware.py)는 ASGI "http" scope만 다뤄서 이
    WebSocket 연결은 지금까지 구조화된 접근 로그에 전혀 남지 않았다 - 이 라우트가
    붙잡고 있는 DB 커넥션/Ollama 클라이언트를 누가(user_id/client IP) 얼마나
    오래 점유했는지, 왜 끊겼는지(유휴 타임아웃/클라이언트 종료/오류) grep 한 줄로
    확인할 방법이 없었다. 같은 "haruhan.access" 로거로 connect/disconnect를
    한 줄씩 남긴다.
    """
    await websocket.accept()
    settings = get_settings()
    max_length = settings.max_prompt_length
    # get_current_user_ws()가 이미 검증했으므로 항상 존재한다.
    token = websocket.query_params.get("token")
    assert token is not None
    client_ip = websocket.client.host if websocket.client else "127.0.0.1"
    connect_time = time.monotonic()
    access_logger.info(
        "ws_event=connect path=%s client=%s user_id=%s", websocket.url.path, client_ip, current_user.id
    )
    disconnect_reason = "client_disconnect"
    try:
        while True:
            try:
                payload = await asyncio.wait_for(
                    websocket.receive_json(), timeout=settings.ws_idle_timeout_seconds
                )
            except asyncio.TimeoutError:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE, reason="idle timeout")
                disconnect_reason = "idle_timeout"
                break
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "잘못된 JSON 형식입니다."})
                continue

            # get_current_user_ws()는 accept() 전 딱 한 번만 토큰을 검증한다 -
            # 그 뒤로는 REST(매 요청마다 get_current_user()가 다시 검증)와
            # 달리 아무도 다시 확인하지 않아, connect 시점엔 유효했던 토큰이
            # 그 사이 만료돼도 계속 인증된 것처럼 메시지를 처리했다(실제
            # 만료된 토큰으로 REST는 401을 내는데 이미 열린 이 연결은 정상
            # 처리하는 것까지 재현해 확인함). 메시지를 처리하기 전마다 매번
            # 다시 확인해, 만료됐으면 REST와 마찬가지로 거부한다.
            if is_ws_token_expired(token, settings):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="token expired")
                disconnect_reason = "token_expired"
                break

            if not isinstance(payload, dict):
                await websocket.send_json({"type": "error", "detail": "잘못된 요청 형식입니다."})
                continue
            content = payload.get("content")
            if not isinstance(content, str) or is_blank(content):
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
            except WebSocketDisconnect:
                # 스트리밍 도중(위 send_json 여러 번 중 아무 데서나) 클라이언트가
                # 사라지면(탭 닫힘, 네트워크 끊김, 모바일 앱 백그라운드 전환 등)
                # Starlette의 WebSocket.send()가 전송 계층의 OSError를 그대로
                # WebSocketDisconnect(code=1006)로 바꿔서 던진다(websockets.py 참고) -
                # 이 예외도 Exception의 하위 클래스라, 아래 `except Exception:`이
                # 아니라 여기서 먼저 잡아야 한다. 여기서 잡지 않으면 아래
                # `except Exception:`이 이걸 "예상 못 한 서버 오류"로 오분류해
                # send_json으로 에러 메시지를 다시 보내려 하는데, 그 시점엔 이미
                # Starlette가 소켓을 DISCONNECTED로 표시해둔 뒤라 그 재전송 시도
                # 자체가 `RuntimeError('Cannot call "send" once a close message
                # has been sent.')`로 실패한다 - 그 어디에도 안 잡혀서 코루틴
                # 밖으로 그대로 새어나간다(184라운드 주석대로 ServerErrorMiddleware
                # 도 websocket scope는 안 건드림). 실제 stream_message를 그대로
                # 호출하면서 두 번째 send_json에서 OSError가 나도록 만들어 이
                # RuntimeError가 실제로 코루틴을 뚫고 나가는 것까지 직접 재현해
                # 확인했다. 여기서 다시 던져 바깥쪽 `except WebSocketDisconnect
                # as exc:`(185라운드가 code로 종료 사유를 구분하도록 고친 바로 그
                # 핸들러)가 정상적인 클라이언트 종료로 분류하게 한다 - 재전송을
                # 시도하지 않는다.
                raise
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
                disconnect_reason = "error"
                return
    except WebSocketDisconnect as exc:
        # uvicorn의 세 WebSocket 프로토콜 구현(websockets/wsproto 계열) 전부
        # 프로세스 종료(SIGTERM, 즉 이 앱을 재배포할 때마다 매번 일어나는 일 -
        # docker-compose.yml이 워커 1개로 uvicorn을 그대로 돌림) 시 살아있는
        # WebSocket 연결에 code=1012("Service Restart")로 직접 종료를 건다 -
        # 클라이언트가 스스로 끊은 게 아니라 서버가 끊은 것이다. 이 예외 자체가
        # 그 코드를 들고 있는데도 기존 코드는 그냥 버리고 항상
        # "client_disconnect"로 남겨서, 재배포로 끊긴 연결과 사용자가 실제로
        # 끊은 연결을 로그만 보고 구분할 수 없었다(173라운드가 이 로그를 만든
        # 목적 자체가 "왜 끊겼는지 grep으로 알아내기"인데 정작 가장 흔하게
        # 대량으로 끊기는 원인 하나를 못 구분함). 실제 uvicorn 프로세스를
        # 띄우고 실제 WebSocket 클라이언트로 연결한 뒤 SIGTERM을 보내
        # 직접 재현해 확인했다 - 클라이언트는 close code 1012를 받고, 서버
        # 로그는 (고치기 전엔) "client_disconnect"로 남았다.
        if exc.code == 1012:
            disconnect_reason = "server_shutdown"
    finally:
        duration_ms = (time.monotonic() - connect_time) * 1000
        access_logger.info(
            "ws_event=disconnect path=%s client=%s user_id=%s duration_ms=%.1f reason=%s",
            websocket.url.path,
            client_ip,
            current_user.id,
            duration_ms,
            disconnect_reason,
        )
