from fastapi import APIRouter, Depends

from app.api.deps import get_chat_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_with_ollama(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
):
    """오라클 서버의 Ollama(Qwen) 모델로 프롬프트를 전달하는 엔드포인트"""
    return await chat_service.chat(request)
