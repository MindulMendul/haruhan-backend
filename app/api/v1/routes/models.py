from fastapi import APIRouter, Depends, HTTPException, status

from app.core.cache import TTLCache
from app.core.dependencies import get_ollama_service
from app.schemas.models import OllamaModelInfo, OllamaModelListResponse
from app.services.ollama_service import OllamaService, OllamaServiceError

router = APIRouter(prefix="/models", tags=["models"])

# 모델 목록은 Ollama에 새 모델을 pull하지 않는 한 안 바뀌므로, 매 요청마다
# 실제 호출하는 대신 짧게 캐시해서 부하를 줄인다.
_MODELS_CACHE_TTL_SECONDS = 60.0
_models_cache: TTLCache[OllamaModelListResponse] = TTLCache(ttl_seconds=_MODELS_CACHE_TTL_SECONDS)


@router.get("", response_model=OllamaModelListResponse)
async def list_models(
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> OllamaModelListResponse:
    """지금 Ollama 엔진에 pull되어 있어 바로 쓸 수 있는 모델 목록.

    프론트가 model 필드를 하드코딩하지 않고 실제 사용 가능한 모델을 받아쓸 수 있게
    한다. 민감 정보가 아니라 인증 없이 공개한다.
    """
    cached = _models_cache.get()
    if cached is not None:
        return cached

    try:
        raw_models = await ollama_service.list_models()
    except OllamaServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    models = [
        OllamaModelInfo(
            name=m.get("name") or m.get("model", ""),
            size=m.get("size"),
            parameter_size=(m.get("details") or {}).get("parameter_size"),
            quantization_level=(m.get("details") or {}).get("quantization_level"),
        )
        for m in raw_models
    ]
    response = OllamaModelListResponse(models=models)
    _models_cache.set(response)
    return response
