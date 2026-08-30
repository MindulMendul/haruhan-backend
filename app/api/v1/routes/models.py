import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.cache import TTLCache
from app.core.config import get_settings
from app.core.dependencies import get_ollama_service
from app.core.rate_limit import limiter
from app.schemas.models import OllamaModelInfo, OllamaModelListResponse
from app.services.ollama_service import OllamaService, OllamaServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])

# 모델 목록은 Ollama에 새 모델을 pull하지 않는 한 안 바뀌므로, 매 요청마다
# 실제 호출하는 대신 짧게 캐시해서 부하를 줄인다.
_MODELS_CACHE_TTL_SECONDS = 60.0
_models_cache: TTLCache[OllamaModelListResponse] = TTLCache(ttl_seconds=_MODELS_CACHE_TTL_SECONDS)
# 캐시가 막 만료된 순간 동시에 들어온 요청들이 캐시 미스를 몰려서 겪으면, 락 없이는
# 각자 독립적으로 Ollama를 호출한다(캐시가 있는 의미가 없어짐) - 미스가 났을 때만
# 이 락을 거쳐 한 요청만 실제로 채우고 나머지는 그 결과를 그대로 받아가게 한다.
_models_cache_lock = asyncio.Lock()


async def _get_or_fetch_models(ollama_service: OllamaService) -> OllamaModelListResponse:
    """캐시에 있으면 그대로 쓰고, 없으면 락을 거쳐 한 호출자만 Ollama를 실제로
    부르고 나머지는 그 결과를 그대로 받아간다 - 캐시가 막 만료된 순간 동시에
    들어온 요청들이 락 없이 각자 독립적으로 Ollama를 호출하는 것(캐시 미스 몰림)
    을 막는다. 라우트 핸들러에서 분리해둔 건, 레이트리밋 데코레이터/Request/
    Response 배선 없이 이 캐시/락 동작 자체만 직접 테스트할 수 있게 하기 위함이다.
    """
    cached = _models_cache.get()
    if cached is not None:
        return cached

    async with _models_cache_lock:
        # 락을 기다리는 동안 다른 요청이 이미 채워놨을 수 있다 - 재확인해서
        # 채워져 있으면 Ollama를 또 부르지 않고 그 결과를 그대로 쓴다.
        cached = _models_cache.get()
        if cached is not None:
            return cached

        try:
            raw_models = await ollama_service.list_models()
        except OllamaServiceError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        # OllamaService.list_models()는 타입 힌트상 list[dict]지만, 그건 업스트림
        # Ollama의 /api/tags가 실제로 그런 형태를 보낸다는 걸 강제하지 않는다 -
        # ollama_service.py의 다른 메서드들은 필드 하나하나가 예상과 다른 형태여도
        # (None, 다른 타입 등) 조용히 안전한 기본값으로 접지만, 이 항목 자체가
        # dict가 아닌 경우(예: 문자열 배열을 보내는 오동작하는 Ollama 포크/프록시나
        # 향후 API 형태 변경)까지는 안 걸러졌다 - 그러면 m.get(...) 자체가
        # AttributeError로 죽어 처리되지 않은 예외(500)가 새어나갔다. 이 앱에서
        # 유일하게 인증 없이 공개된 엔드포인트라 그 크래시가 _models_cache.set()
        # 이전에 나서 캐시도 못 채우고, 매 요청마다 같은 크래시와 함께 Ollama를
        # 다시 호출해(캐시/락 코얼레싱이 이 실패 모드에서는 완전히 무력화됨) 다른
        # 모든 Ollama 실패 경로와 같은 502가 아니라 500으로 오분류된다.
        models = []
        for m in raw_models:
            if not isinstance(m, dict):
                logger.warning("Ollama /api/tags 응답에 예상과 다른 형식의 항목이 있어 건너뜁니다: %r", m)
                continue
            models.append(
                OllamaModelInfo(
                    name=m.get("name") or m.get("model", ""),
                    size=m.get("size"),
                    parameter_size=(m.get("details") or {}).get("parameter_size"),
                    quantization_level=(m.get("details") or {}).get("quantization_level"),
                )
            )
        result = OllamaModelListResponse(models=models)
        _models_cache.set(result)
        return result


@router.get("", response_model=OllamaModelListResponse)
@limiter.limit(lambda: get_settings().models_rate_limit)
async def list_models(
    request: Request,
    response: Response,
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> OllamaModelListResponse:
    """지금 Ollama 엔진에 pull되어 있어 바로 쓸 수 있는 모델 목록.

    프론트가 model 필드를 하드코딩하지 않고 실제 사용 가능한 모델을 받아쓸 수 있게
    한다. 민감 정보가 아니라 인증 없이 공개한다 - 그래서 이 앱에서 유일하게
    인증 없이 열려 있는 엔드포인트라, 익명 호출자가 원하는 만큼 반복 호출하는
    것을 막을 다른 수단이 없다. 대부분의 요청은 60초 캐시로 막히지만, 그것만으로는
    (a) 캐시가 있어도 반복 호출 자체를 막지는 못하고(레이트리밋이 필요한 이유),
    (b) 캐시가 막 만료된 순간 동시에 온 요청은 전부 캐시 미스를 겪어 각자 Ollama를
    직접 호출한다(_get_or_fetch_models의 락이 막는 이유) - 두 문제 모두 실제로는
    이 60초 캐시가 거의 무의미해지는 방향으로 새는 구멍이었다.
    """
    return await _get_or_fetch_models(ollama_service)
