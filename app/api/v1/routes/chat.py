import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.core.dependencies import get_ollama_service
from app.core.rate_limit import limiter
from app.core.security import verify_api_key
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ollama_service import OllamaService, OllamaServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(verify_api_key)])

# interview_practice_service.py의 _generate_first_question/_generate_feedback_text와
# 같은 상수/이유 (아래 루프 주석 참고).
_MAX_GENERATION_ATTEMPTS = 2


@router.post("", response_model=ChatResponse)
@limiter.limit(lambda: get_settings().chat_rate_limit)
async def chat_with_ollama(
    request: Request,
    response: Response,
    payload: ChatRequest,
    ollama_service: OllamaService = Depends(get_ollama_service),
) -> ChatResponse:
    """오라클 서버의 Ollama(Qwen) 모델로 프롬프트를 전달하는 엔드포인트."""
    # ollama_service.generate()는 Ollama가 200을 응답해도 본문에 response 키가
    # 없거나 모델이 빈/공백 텍스트만 뱉으면 예외를 던지지 않고 그냥 빈 문자열을
    # 돌려준다(ollama_service.py의 generate() 주석 참고) - 188라운드가 study_
    # service/interview_practice_service 등 다른 모든 generate()/chat() 호출부에
    # 재시도+공백 검증을 추가했는데, 이 범용 프록시 엔드포인트만 그 대상에서
    # 빠져 있었다. 검증 없이 그대로 반환하면 이 API를 쓰는 클라이언트는 "모델이
    # 정말 빈 답을 했다"와 "호출 자체가 사실상 실패했다"를 구분할 방법 없이
    # 200 { "result": "" }를 받는다.
    for attempt in range(1, _MAX_GENERATION_ATTEMPTS + 1):
        try:
            result = await ollama_service.generate(prompt=payload.prompt, model=payload.model)
        except OllamaServiceError as exc:
            # study_service/quiz_service/interview_practice_service/interview_review_service/
            # models 라우트는 전부 Ollama 호출 실패를 502(우리 서버가 아니라 업스트림 AI
            # 엔진의 문제)로 응답한다 - 이 라우트만 500이면 상태 코드로 분기하는 프론트가
            # 업스트림 장애를 "우리 서버 버그"로 잘못 분류하게 된다.
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        if result.strip():
            return ChatResponse(result=result)
        logger.warning("/chat 응답 생성 검증 실패 (시도 %d/%d): 공백뿐임", attempt, _MAX_GENERATION_ATTEMPTS)

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY, detail="AI 응답 생성에 실패했습니다. 다시 시도해주세요."
    )
