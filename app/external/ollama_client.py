import httpx

from app.core.config import settings
from app.core.logging import logger


class OllamaClient:
    def __init__(self, base_url: str | None = None, timeout: float = 60.0):
        self.base_url = base_url or settings.ollama_base_url
        self.timeout = timeout

    async def generate(self, model: str, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                logger.error(f"Ollama API 호출 에러: {e}")
                raise
            data = response.json()
            return data.get("response", "")
