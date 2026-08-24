import asyncio
import json
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
)
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
    """
    await websocket.accept()
    settings = get_settings()
    client_ip = websocket.client.host if websocket.client else "127.0.0.1"
    try:
        while True:
            try:
                raw_payload = await asyncio.wait_for(
                    websocket.receive_json(), timeout=settings.ws_idle_timeout_seconds
                )
            except asyncio.TimeoutError:
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE, reason="idle timeout")
                break
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "잘못된 JSON 형식입니다."})
                continue
            try:
                payload = InterviewReviewCreateRequest.model_validate(raw_payload)
            except ValidationError as exc:
                await websocket.send_json({"type": "error", "detail": str(exc)})
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
    except WebSocketDisconnect:
        pass
