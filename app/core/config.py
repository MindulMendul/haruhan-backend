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

    # 로그인/회원가입/비밀번호 변경처럼 브루트포스 대상이 될 수 있는 엔드포인트용 제한.
    # LLM 호출 비용 때문에 두는 chat_rate_limit과는 성격이 달라 분리해둔다.
    auth_rate_limit: str = "5/minute"

    # 요청 바디 최대 크기 (바이트). 기본 1MB.
    max_body_size_bytes: int = 1_048_576

    # 설정하면 slowapi 레이트 리밋이 Redis를 공유 스토리지로 사용한다 (다중 워커/인스턴스 환경용).
    # 비워두면 인메모리 스토리지를 사용한다 (단일 프로세스에서만 정확함).
    redis_url: str | None = None

    # JWT 서명 키. 안전한 기본값이 존재하지 않으므로 필수값으로 둔다 (미설정 시 앱이 시작되지 않음).
    # openssl rand -hex 32 등으로 생성해서 설정할 것.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # 퀴즈 생성 소스 텍스트 최대 길이 (문자 수). 학습 세션 전체를 소스로 쓸 수 있어
    # 일반 프롬프트(max_prompt_length)보다 넉넉하게 둔다.
    max_quiz_source_length: int = 20_000
    default_quiz_question_count: int = 5
    max_quiz_question_count: int = 20

    # 면접 연습 세션 하나당 최대 질문 수. 도달하면 다음 질문을 생성하지 않고
    # 클라이언트가 /complete를 호출해 종합 피드백을 받도록 유도한다.
    max_interview_questions: int = 5

    # 면접 복기 content 최대 길이 (문자 수).
    max_review_content_length: int = 10_000

    # RAG 검색용 임베딩 모델. Ollama에 별도로 pull 되어 있어야 한다.
    embedding_model: str = "nomic-embed-text"
    # 학습챗 답변 생성 시 참고자료로 첨부할 최대 청크 개수.
    rag_top_k: int = 3

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
