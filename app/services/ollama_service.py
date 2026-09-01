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
        # 메서드마다 새 httpx.AsyncClient를 만들면 호출할 때마다 TCP 연결을 새로
        # 맺었다 끊는다 - 이 인스턴스의 수명 동안(요청 하나, 혹은 WebSocket
        # 연결 하나) 공유하는 클라이언트 하나로 커넥션을 재사용한다. FastAPI
        # 의존성(get_ollama_service)이 요청/연결이 끝나면 aclose()로 정리한다.
        self._client = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def generate(self, prompt: str, model: str) -> str:
        """오라클 서버의 Ollama(Qwen) 모델로 프롬프트를 전달하고 응답 텍스트를 반환한다."""
        try:
            response = await self._client.post(
                f"{self._base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            # dict.get(key, default)는 key가 아예 없을 때만 default를 쓴다 - Ollama가
            # (혹은 앞단 프록시가) `{"response": null}`처럼 key는 있는데 값이 JSON
            # null인 응답을 주면 그대로 None이 반환된다. 이 메서드의 반환 타입은
            # `str`로 선언돼 있고 호출부(interview_practice_service.py 등)는
            # `.strip()`으로 공백 여부만 확인하지 None 여부는 확인하지 않아
            # (rounds 172/173이 만든 재시도+공백 검증 전제 자체가 "항상 str"이므로),
            # None이 그대로 새어나가면 AttributeError로 재시도 없이 바로 죽는다 -
            # `or ""`로 None도 빈 문자열로 접어서 이 메서드가 항상 실제로 `str`을
            # 반환한다는 반환 타입 선언의 약속을 지킨다.
            return response.json().get("response") or ""
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            # HTTP 상태 에러뿐 아니라, 200을 받았어도 본문이 JSON이 아닌 경우
            # (Ollama 앞단 프록시 오작동, 응답이 중간에 끊기는 경우 등)도 같은
            # OllamaServiceError로 묶는다 - response.json()이 try 밖에 있으면
            # JSONDecodeError가 그대로 새어나가 이 메서드의 나머지 실패
            # 경로와 다르게 처리되지 않은 예외로 잡힌다.
            logger.error("Ollama API 호출 에러: %s", exc)
            raise OllamaServiceError("Ollama 엔진 응답 실패") from exc

    async def chat(self, messages: list[dict[str, str]], model: str) -> str:
        """멀티턴 대화용: role/content 히스토리를 그대로 Ollama /api/chat에 전달한다."""
        try:
            response = await self._client.post(
                f"{self._base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": False},
            )
            response.raise_for_status()
            # generate()와 같은 이유(위 주석 참고) - message나 message.content가
            # 명시적 null이어도 None이 아니라 항상 str을 반환하도록 접는다.
            return (response.json().get("message") or {}).get("content") or ""
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.error("Ollama API 호출 에러: %s", exc)
            raise OllamaServiceError("Ollama 엔진 응답 실패") from exc

    async def chat_stream(self, messages: list[dict[str, str]], model: str) -> AsyncIterator[str]:
        """chat()의 스트리밍 버전. 응답을 토큰(조각) 단위로 하나씩 yield한다.

        Ollama는 stream=True일 때 개행으로 구분된 JSON(ndjson)을 한 줄씩 보낸다.
        각 줄이 delta 하나를 담고 있고, done=true인 줄로 스트림이 끝난다.
        """
        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json={"model": model, "messages": messages, "stream": True},
            ) as response:
                response.raise_for_status()
                saw_done = False
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        # Ollama는 이미 200 헤더를 보내고 스트리밍을 시작한 뒤
                        # 모델 실행이 죽으면(OOM, 컨텍스트 초과 등) HTTP 상태로는
                        # 더 이상 실패를 알릴 방법이 없어, message/done 없이
                        # {"error": ...} 한 줄만 보내고 연결을 끊는다. 이 줄을
                        # content/done 어느 쪽으로도 인식하지 못하고 그냥
                        # 지나치면 스트림이 "조용히" 끝나버려서, 지금까지 모은
                        # 부분 응답을 study_service.stream_message/interview_
                        # review_service.stream_create_review가 정상 완료로
                        # 착각해 그대로 커밋하고 클라이언트에 "done"으로 보낸다
                        # - 실제 mock 전송으로 재현해 확인했다. 다른 메서드들과
                        # 같은 OllamaServiceError로 묶어 호출부가 이미 갖춘
                        # 실패 처리 경로(_GENERATION_FAILED)를 타게 한다.
                        raise OllamaServiceError(f"Ollama 스트리밍 응답 오류: {chunk['error']}")
                    content = (chunk.get("message") or {}).get("content") or ""
                    if content:
                        yield content
                    if chunk.get("done"):
                        saw_done = True
                        break
                if not saw_done:
                    # 명시적 {"error": ...} 줄 없이 연결만 끊기는 경우(프록시가
                    # 스트림을 중간에서 자르는 등)도 done=true를 못 봤다는 점은
                    # 같다 - 위와 같은 이유로 partial 응답을 성공으로 착각하지
                    # 않도록 실패로 취급한다.
                    raise OllamaServiceError("Ollama 스트리밍이 완료되지 않고 중간에 끊겼습니다")
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.error("Ollama 스트리밍 API 호출 에러: %s", exc)
            raise OllamaServiceError("Ollama 엔진 응답 실패") from exc

    async def embed(self, text: str, model: str) -> list[float]:
        """텍스트를 임베딩 벡터로 변환한다 (RAG 검색용)."""
        try:
            response = await self._client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": model, "prompt": text},
            )
            response.raise_for_status()
            # generate()와 같은 이유(그 메서드의 주석 참고) - embedding이 명시적
            # null이어도 None이 아니라 항상 list를 반환하도록 접는다.
            return response.json().get("embedding") or []
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.error("Ollama API 호출 에러: %s", exc)
            raise OllamaServiceError("Ollama 엔진 응답 실패") from exc

    async def list_models(self) -> list[dict]:
        """Ollama 엔진에 pull되어 있는(=바로 쓸 수 있는) 모델 목록을 그대로 반환한다."""
        try:
            response = await self._client.get(f"{self._base_url}/api/tags")
            response.raise_for_status()
            # generate()와 같은 이유(그 메서드의 주석 참고) - models가 명시적
            # null이어도 None이 아니라 항상 list를 반환하도록 접는다.
            return response.json().get("models") or []
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.error("Ollama API 호출 에러: %s", exc)
            raise OllamaServiceError("Ollama 엔진 응답 실패") from exc

    async def generate_json(self, prompt: str, model: str, schema: dict) -> str:
        """JSON 스키마로 출력 형식을 강제한다 (Ollama structured outputs).

        모델이 자유 텍스트 대신 스키마에 맞는 JSON만 생성하도록 constrained decoding을
        건다. 퀴즈 문제처럼 파싱 가능한 구조화 데이터가 필요할 때 사용한다.
        """
        try:
            response = await self._client.post(
                f"{self._base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "format": schema},
            )
            response.raise_for_status()
            # generate()와 같은 이유(그 메서드의 주석 참고) - response가 명시적
            # null이어도 None이 아니라 항상 str을 반환하도록 접는다.
            return response.json().get("response") or ""
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.error("Ollama API 호출 에러: %s", exc)
            raise OllamaServiceError("Ollama 엔진 응답 실패") from exc
