import logging

import httpx

logger = logging.getLogger(__name__)


class OllamaServiceError(Exception):
    """Ollama 엔진 호출이 실패했을 때 발생한다."""


class OllamaService:
    def __init__(self, base_url: str, timeout: float = 60.0) -> None:
        self._base_url = base_url
        self._timeout = timeout

    async def generate(self, prompt: str, model: str) -> str:
        """오라클 서버의 Ollama(Qwen) 모델로 프롬프트를 전달하고 응답 텍스트를 반환한다."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("Ollama API 호출 에러: %s", exc)
                raise OllamaServiceError("Ollama 엔진 응답 실패") from exc
        return response.json().get("response", "")

    async def chat(self, messages: list[dict[str, str]], model: str) -> str:
        """멀티턴 대화용: role/content 히스토리를 그대로 Ollama /api/chat에 전달한다."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json={"model": model, "messages": messages, "stream": False},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("Ollama API 호출 에러: %s", exc)
                raise OllamaServiceError("Ollama 엔진 응답 실패") from exc
        return response.json().get("message", {}).get("content", "")
