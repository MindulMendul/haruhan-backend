from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    app_name: str = "Haruhan Backend"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # 콤마로 구분된 origin 목록. 비어있으면 모든 cross-origin 요청을 차단한다(안전한 기본값).
    cors_origins: str = ""

    # 설정되지 않으면 /api/chat 인증이 비활성화된다 (개발 편의용, 운영 환경에서는 반드시 설정할 것).
    api_key: str | None = None

    chat_rate_limit: str = "10/minute"
    max_prompt_length: int = 4000

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
