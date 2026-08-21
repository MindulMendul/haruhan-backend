from pydantic import BaseModel


class OllamaModelInfo(BaseModel):
    name: str
    size: int | None = None
    parameter_size: str | None = None
    quantization_level: str | None = None


class OllamaModelListResponse(BaseModel):
    models: list[OllamaModelInfo]
