import json
import logging
from collections.abc import AsyncIterator

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

    async def chat_stream(self, messages: list[dict[str, str]], model: str) -> AsyncIterator[str]:
        """chat()의 스트리밍 버전. 응답을 토큰(조각) 단위로 하나씩 yield한다.

        Ollama는 stream=True일 때 개행으로 구분된 JSON(ndjson)을 한 줄씩 보낸다.
        각 줄이 delta 하나를 담고 있고, done=true인 줄로 스트림이 끝난다.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/api/chat",
                    json={"model": model, "messages": messages, "stream": True},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
                        if chunk.get("done"):
                            break
        except httpx.HTTPError as exc:
            logger.error("Ollama 스트리밍 API 호출 에러: %s", exc)
            raise OllamaServiceError("Ollama 엔진 응답 실패") from exc

    async def embed(self, text: str, model: str) -> list[float]:
        """텍스트를 임베딩 벡터로 변환한다 (RAG 검색용)."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": model, "prompt": text},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("Ollama API 호출 에러: %s", exc)
                raise OllamaServiceError("Ollama 엔진 응답 실패") from exc
        return response.json().get("embedding", [])

    async def list_models(self) -> list[dict]:
        """Ollama 엔진에 pull되어 있는(=바로 쓸 수 있는) 모델 목록을 그대로 반환한다."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("Ollama API 호출 에러: %s", exc)
                raise OllamaServiceError("Ollama 엔진 응답 실패") from exc
        return response.json().get("models", [])

    async def generate_json(self, prompt: str, model: str, schema: dict) -> str:
        """JSON 스키마로 출력 형식을 강제한다 (Ollama structured outputs).

        모델이 자유 텍스트 대신 스키마에 맞는 JSON만 생성하도록 constrained decoding을
        건다. 퀴즈 문제처럼 파싱 가능한 구조화 데이터가 필요할 때 사용한다.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False, "format": schema},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("Ollama API 호출 에러: %s", exc)
                raise OllamaServiceError("Ollama 엔진 응답 실패") from exc
        return response.json().get("response", "")
