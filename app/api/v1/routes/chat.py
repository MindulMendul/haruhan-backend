from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.core.dependencies import get_ollama_service
from app.core.rate_limit import limiter
from app.core.security import verify_api_key
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ollama_service import OllamaService, OllamaServiceError

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(verify_api_key)])


@router.post("", response_model=ChatResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def chat_with_ollama(
    request: Request,
    response: Response,
    payload: ChatRequest,
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> ChatResponse:
    """오라클 서버의 Ollama(Qwen) 모델로 프롬프트를 전달하는 엔드포인트."""
    try:
        result = await ollama_service.generate(prompt=payload.prompt, model=payload.model)
    except OllamaServiceError as exc:
        # study_service/quiz_service/interview_practice_service/interview_review_service/
        # models 라우트는 전부 Ollama 호출 실패를 502(우리 서버가 아니라 업스트림 AI
        # 엔진의 문제)로 응답한다 - 이 라우트만 500이면 상태 코드로 분기하는 프론트가
        # 업스트림 장애를 "우리 서버 버그"로 잘못 분류하게 된다.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return ChatResponse(result=result)
