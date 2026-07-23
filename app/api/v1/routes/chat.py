from fastapi import APIRouter, Depends, HTTPException, Request

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
    payload: ChatRequest,
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> ChatResponse:
    """오라클 서버의 Ollama(Qwen) 모델로 프롬프트를 전달하는 엔드포인트."""
    try:
        result = await ollama_service.generate(prompt=payload.prompt, model=payload.model)
    except OllamaServiceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(result=result)
