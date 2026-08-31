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
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import (
    get_current_user,
    get_current_user_ws,
    get_ollama_service,
    get_rag_service,
    limit_ws_connections,
)
from app.core.errors import sanitize_pydantic_errors
from app.core.middleware import access_logger
from app.core.rate_limit import check_rate_limit, limiter
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.interview_review import (
    InterviewReviewCreateRequest,
    InterviewReviewResponse,
    InterviewReviewUpdateRequest,
)
from app.services.interview_review_service import InterviewReviewService
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview/reviews", tags=["interview-review"])


def get_interview_review_service(
    session: AsyncSession = Depends(get_db),
    ollama_service: OllamaService = Depends(get_ollama_service),
    rag_service: RagService = Depends(get_rag_service),
) -> InterviewReviewService:
    return InterviewReviewService(session=session, ollama_service=ollama_service, rag_service=rag_service)


@router.post("", response_model=InterviewReviewResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def create_review(
    request: Request,
    response: Response,
    payload: InterviewReviewCreateRequest,
    current_user: User = Depends(get_current_user),
    service: InterviewReviewService = Depends(get_interview_review_service),
) -> InterviewReviewResponse:
    review = await service.create_review(
        user_id=current_user.id,
        company=payload.company,
        position=payload.position,
        interview_date=payload.interview_date,
        content=payload.content,
        model=payload.model,
    )
    return InterviewReviewResponse.model_validate(review)


@router.get("", response_model=list[InterviewReviewResponse])
async def list_reviews(
    response: Response,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    service: InterviewReviewService = Depends(get_interview_review_service),
) -> list[InterviewReviewResponse]:
    reviews, total = await service.list_reviews(user_id=current_user.id, limit=limit, offset=offset)
    response.headers["X-Total-Count"] = str(total)
    return [InterviewReviewResponse.model_validate(r) for r in reviews]


@router.get("/{review_id}", response_model=InterviewReviewResponse)
async def get_review(
    review_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: InterviewReviewService = Depends(get_interview_review_service),
) -> InterviewReviewResponse:
    review = await service.get_review(review_id=review_id, user_id=current_user.id)
    return InterviewReviewResponse.model_validate(review)


@router.patch("/{review_id}", response_model=InterviewReviewResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def update_review(
    request: Request,
    response: Response,
    review_id: uuid.UUID,
    payload: InterviewReviewUpdateRequest,
    current_user: User = Depends(get_current_user),
    service: InterviewReviewService = Depends(get_interview_review_service),
) -> InterviewReviewResponse:
    review = await service.update_review(
        review_id=review_id,
        user_id=current_user.id,
        company=payload.company,
        position=payload.position,
        interview_date=payload.interview_date,
        content=payload.content,
    )
    return InterviewReviewResponse.model_validate(review)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: InterviewReviewService = Depends(get_interview_review_service),
) -> None:
    await service.delete_review(review_id=review_id, user_id=current_user.id)


@router.websocket("/stream")
async def stream_create_review(
    websocket: WebSocket,
    _connection_slot: None = Depends(limit_ws_connections),
    current_user: User = Depends(get_current_user_ws),
    service: InterviewReviewService = Depends(get_interview_review_service),
) -> None:
    """create_review의 스트리밍 버전. 인증은 쿼리 파라미터(?token=...)로 받는다 -
    브라우저 WebSocket API가 커스텀 헤더를 지원하지 않기 때문이다.

    클라이언트가 POST /interview/reviews와 같은 필드({"company", "position",
    "interview_date", "content", "model"?})를 보내면, 서버는
    {"type": "delta", "content": "..."}*를 이어보내다가
    {"type": "done", "data": {...InterviewReviewResponse}}를 보낸다. 검증/생성
    실패는 {"type": "error", "detail": "..."} (연결은 끊기지 않음).

    기존 REST 엔드포인트(POST /interview/reviews)는 그대로 남겨둔다. 면접복기
    AI 피드백은 전체 복기 내용을 분석하는, 이 서비스에서 가장 긴 텍스트 생성이라
    스트리밍 가치가 크다고 판단해 학습챗과 같은 패턴으로 추가했다 - 수정
    시 피드백을 재생성하는 PATCH 흐름은 상대적으로 드문 케이스라 이번 범위에
    넣지 않았다.

    클라이언트가 ws_idle_timeout_seconds(기본 5분) 동안 메시지를 하나도 안 보내면
    연결을 끊는다 - 이 연결이 붙잡고 있는 DB 커넥션/Ollama 클라이언트를 방치된
    연결이 무한정 점유해 커넥션 풀을 고갈시키는 것을 막기 위함이다.

    방치된 연결뿐 아니라 활발하게 메시지를 주고받는 연결도(학습챗 스트리밍과
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
    client_ip = websocket.client.host if websocket.client else "127.0.0.1"
    connect_time = time.monotonic()
    access_logger.info(
        "ws_event=connect path=%s client=%s user_id=%s", websocket.url.path, client_ip, current_user.id
    )
    disconnect_reason = "client_disconnect"
    try:
        while True:
            try:
                raw_payload = await asyncio.wait_for(
                    websocket.receive_json(), timeout=settings.ws_idle_timeout_seconds
                )
            except asyncio.TimeoutError:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE, reason="idle timeout")
                disconnect_reason = "idle_timeout"
                break
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "잘못된 JSON 형식입니다."})
                continue
            try:
                payload = InterviewReviewCreateRequest.model_validate(raw_payload)
            except ValidationError as exc:
                # ValidationError.__str__()/str(exc)에는 검증에 실패한 필드의 원본 입력값이
                # 그대로 포함된다 - REST 쪽 422 응답이 이미 이 이유로 input을 제거하는데
                # (app.core.errors.validation_exception_handler), 이 WS 경로는 FastAPI의
                # 자동 검증을 안 타고 model_validate()를 직접 호출해서 그 sanitization을
                # 거치지 않았다. 같은 헬퍼로 필드 위치/에러 종류/메시지만 남긴다.
                messages = [
                    f"{'.'.join(str(p) for p in error['loc'])}: {error['msg']}"
                    for error in sanitize_pydantic_errors(exc.errors())
                ]
                await websocket.send_json({"type": "error", "detail": "; ".join(messages)})
                continue

            allowed, retry_after = check_rate_limit(
                f"ws:interview-review:{client_ip}", get_settings().chat_rate_limit
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
                async for event_type, data in service.stream_create_review(
                    user_id=current_user.id,
                    company=payload.company,
                    position=payload.position,
                    interview_date=payload.interview_date,
                    content=payload.content,
                    model=payload.model,
                ):
                    if event_type == "delta":
                        await websocket.send_json({"type": "delta", "content": data})
                    elif event_type == "done":
                        await websocket.send_json(
                            {
                                "type": "done",
                                "data": InterviewReviewResponse.model_validate(data).model_dump(mode="json"),
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
                logger.exception("스트리밍 중 처리되지 않은 예외 발생: user_id=%s", current_user.id)
                await websocket.send_json({"type": "error", "detail": "면접복기 생성 중 오류가 발생했습니다."})
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                disconnect_reason = "error"
                return
    except WebSocketDisconnect as exc:
        # uvicorn의 세 WebSocket 프로토콜 구현(websockets/wsproto 계열) 전부
        # 프로세스 종료(SIGTERM, 즉 이 앱을 재배포할 때마다 매번 일어나는 일 -
        # docker-compose.yml이 워커 1개로 uvicorn을 그대로 돌림) 시 살아있는
        # WebSocket 연결에 code=1012("Service Restart")로 직접 종료를 건다 -
        # 클라이언트가 스스로 끊은 게 아니라 서버가 끊은 것이다. study.py의
        # stream_message와 같은 이유(그쪽 주석 참고, 실제 uvicorn 프로세스로
        # 직접 재현해 확인함)로 이 코드를 구분해서 남긴다.
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
