from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str = Field(default="qwen2.5:3b", max_length=100)

    @field_validator("prompt")
    @classmethod
    def validate_prompt_length(cls, value: str) -> str:
        max_length = get_settings().max_prompt_length
        if len(value) > max_length:
            raise ValueError(f"prompt는 최대 {max_length}자까지 허용됩니다.")
        return value


class ChatResponse(BaseModel):
    result: str
