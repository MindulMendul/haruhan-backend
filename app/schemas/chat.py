from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.schemas.validators import is_blank


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str = Field(default="qwen2.5:3b", max_length=100)

    @field_validator("prompt")
    @classmethod
    def validate_prompt_length(cls, value: str) -> str:
        # min_length=1은 빈 문자열("")만 막을 뿐 "   "처럼 공백만 있는 값은 그대로
        # 통과시킨다 - study.py의 validate_content_length(121라운드)와 같은
        # 이유로, 통과하면 무의미한 프롬프트로 Ollama 호출만 낭비하게 된다.
        # 학습챗/면접연습/면접복기/퀴즈의 프롬프트 필드는 이미 121/151라운드가
        # 이 검증을 추가했는데, 이 범용 프록시 엔드포인트만 빠져 있었다.
        if is_blank(value):
            raise ValueError("prompt는 비어 있을 수 없습니다.")
        max_length = get_settings().max_prompt_length
        if len(value) > max_length:
            raise ValueError(f"prompt는 최대 {max_length}자까지 허용됩니다.")
        return value


class ChatResponse(BaseModel):
    result: str
