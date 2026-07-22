import httpx
from fastapi import HTTPException

from app.external.ollama_client import OllamaClient
from app.schemas.chat import ChatRequest, ChatResponse


class ChatService:
    def __init__(self, ollama_client: OllamaClient | None = None):
        self.ollama_client = ollama_client or OllamaClient()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        try:
            result = await self.ollama_client.generate(request.model, request.prompt)
        except httpx.HTTPError:
            raise HTTPException(status_code=500, detail="Ollama 엔진 응답 실패")
        return ChatResponse(result=result)
