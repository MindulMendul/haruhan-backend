from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_ollama_service
from app.schemas.models import OllamaModelInfo, OllamaModelListResponse
from app.services.ollama_service import OllamaService, OllamaServiceError

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=OllamaModelListResponse)
async def list_models(
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> OllamaModelListResponse:
    """지금 Ollama 엔진에 pull되어 있어 바로 쓸 수 있는 모델 목록.

    프론트가 model 필드를 하드코딩하지 않고 실제 사용 가능한 모델을 받아쓸 수 있게
    한다. 민감 정보가 아니라 인증 없이 공개한다.
    """
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
    return OllamaModelListResponse(models=models)
