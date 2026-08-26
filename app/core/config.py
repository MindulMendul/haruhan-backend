from functools import lru_cache

from limits.util import parse_many
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_MIN_JWT_SECRET_KEY_LENGTH = 32
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_VALID_ENVIRONMENTS = {"development", "production"}


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

    # 학습챗 한 세션의 대화가 길어질수록 send_message/stream_message가 매번 그
    # 세션의 전체 메시지 히스토리를 그대로 Ollama 프롬프트에 다시 실어 보낸다 -
    # 대화가 계속될수록 한 번의 호출에 드는 토큰 수가 무한정 늘어나서, 언젠가
    # 모델의 컨텍스트 윈도우를 넘기면 앞부분이 조용히 잘리거나 응답 품질/지연이
    # 나빠진다. 가장 최근 이 개수만큼의 메시지만 골라 프롬프트에 포함한다
    # (0 이하로 설정하면 히스토리 없이 이번 메시지만 보낸다).
    max_chat_history_messages: int = 40

    # 로그인/회원가입/비밀번호 변경처럼 브루트포스 대상이 될 수 있는 엔드포인트용 제한.
    # LLM 호출 비용 때문에 두는 chat_rate_limit과는 성격이 달라 분리해둔다.
    auth_rate_limit: str = "5/minute"

    # 데이터 export(/export/me)용 제한. 학습챗/퀴즈/면접연습/면접복기 전체 기록을
    # 페이지네이션 없이 한 번에 조회하는 유일한 엔드포인트라, LLM 호출 비용이나
    # 브루트포스와는 다른 이유(무제한 반복 호출 시 계정 이력 크기에 비례하는 DB
    # 부하)로 별도로 분리해둔다.
    export_rate_limit: str = "10/minute"

    # 모델 목록 조회(/models)용 제한. 이 앱에서 인증 없이 공개된 유일한 엔드포인트라
    # (민감 정보가 아니라 의도적으로 그렇게 둠) 레이트리밋이 아예 없으면 익명
    # 호출자가 원하는 만큼 반복 호출할 수 있다 - 대부분은 60초 TTL 캐시로
    # 막히지만, 캐시가 막 만료된 순간 동시에 들어온 요청들은 각자 Ollama를
    # 직접 호출한다(캐시 미스 몰림). LLM 호출 자체가 아니라 목록 조회일
    # 뿐이라 chat_rate_limit보다는 넉넉하게 잡는다.
    models_rate_limit: str = "30/minute"

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
    # 문항 하나당 보기(choices) 개수 상한 - AI가 생성한 퀴즈 검증용 안전장치.
    # max_quiz_question_count와 마찬가지로 사용자 요청 시점(question_count)에만
    # 걸리던 상한이 AI 출력(모델이 실제로 몇 문항/몇 보기를 뱉는지)에는 전혀
    # 적용되지 않던 신뢰 경계 공백을 메운다 - 프롬프트로 "부탁"할 뿐 구조적으로
    # 강제되지 않으므로, 응답 payload 비대화/DB 행 폭증을 막는 최후의 안전장치다.
    max_quiz_choice_count: int = 8

    # 면접 연습 세션 하나당 최대 질문 수. 도달하면 다음 질문을 생성하지 않고
    # 클라이언트가 /complete를 호출해 종합 피드백을 받도록 유도한다.
    max_interview_questions: int = 5

    # 면접 복기 content 최대 길이 (문자 수).
    max_review_content_length: int = 10_000

    # RAG 검색용 임베딩 모델. Ollama에 별도로 pull 되어 있어야 한다.
    embedding_model: str = "nomic-embed-text"
    # 학습챗 답변 생성 시 참고자료로 첨부할 최대 청크 개수.
    rag_top_k: int = 3
    # retrieve_relevant()가 코사인 유사도 채점 대상으로 삼는 후보 청크 수의
    # 상한. 색인된 청크(학습챗 메시지/퀴즈 소스/면접복기)는 만료/정리 로직이
    # 없어 계정이 오래될수록 계속 쌓이기만 하는데, 원래는 이 후보 전체를 매
    # 채팅/면접연습 턴마다 DB에서 통째로 읽어와 채점했다 - 이 값은 그 조회
    # 자체를 최근 것부터 이 개수만큼으로 제한하는 안전장치다. RAG는 원래
    # "가장 관련 있는" 청크를 찾는 게 목적이라 최신순 제한은 이론적으로는
    # 오래된(하지만 더 관련 있을 수 있는) 자료를 검색 대상에서 제외할 수
    # 있지만, 기본값(2000)은 현실적인 사용량보다 훨씬 크게 잡아 정상적인
    # 계정에서는 사실상 아무 영향이 없고 극단적으로 커진 계정에 대한
    # 최후 방어선 역할만 한다 - 퀴즈 생성 시 학습 세션 소스가 너무 길면
    # 가장 최근 대화만 남기는 것(max_quiz_source_length)과 같은 절충이다.
    # 데이터 규모가 실제로 이 상한에 자주 걸릴 정도가 되면, 임베딩을 그대로
    # JSON으로 저장해 파이썬에서 전수 비교하는 지금 방식 자체를 pgvector
    # 같은 벡터 인덱스로 옮기는 게 근본적인 해결책이다(knowledge_chunk.py
    # 모델 주석 참고).
    rag_max_candidate_chunks: int = 2000

    # WebSocket 스트리밍 엔드포인트(학습챗/면접복기)가 클라이언트로부터 다음
    # 메시지를 이 시간(초) 안에 못 받으면 연결을 끊는다. get_db/get_ollama_service
    # 의존성은 WebSocket 연결이 살아있는 동안 DB 커넥션 풀의 커넥션 하나와 Ollama
    # httpx 클라이언트를 계속 붙잡고 있는데, 클라이언트가 접속만 해두고 메시지를
    # 영영 안 보내면(느린 네트워크, 방치, 또는 의도적 남용) 이 자원이 무한정
    # 잠긴다 - DB 풀 크기(기본 pool_size=5 + max_overflow=5 = 10)보다 적은 수의
    # 이런 방치된 연결만으로도 풀 전체가 고갈되어 다른 모든 요청이 막힐 수 있다.
    ws_idle_timeout_seconds: float = 300.0

    # 동시에 열 수 있는 WebSocket 연결(학습챗/면접복기 스트리밍 합산) 수의 상한.
    # 위 ws_idle_timeout_seconds는 "방치된" 연결이 DB 커넥션을 무한정 붙잡는
    # 것만 막을 뿐, 클라이언트가 메시지를 계속 보내 "방치"로 안 잡히는 활성
    # 연결을 동시에 여러 개(풀 크기보다 많이) 열어버리는 것까지는 막지 못한다 -
    # WebSocket 연결 하나가 accept부터 종료까지 DB 커넥션 풀의 커넥션 하나를
    # 계속 점유하므로(get_db가 연결 전체 수명 동안 열려 있는 FastAPI yield
    # 의존성이라, 메시지 하나 처리할 때만 잠깐 빌리는 게 아님), 풀 크기(기본
    # pool_size=5 + max_overflow=5 = 10)보다 많은 동시 연결이 열리면 풀 전체가
    # 고갈돼 이 WebSocket 라우트뿐 아니라 앱의 다른 모든 HTTP/WebSocket 요청까지
    # 막힌다. 기본값(6)은 풀 용량보다 낮게 잡아, 일반 HTTP 트래픽이 쓸 여유
    # 커넥션을 남겨둔다.
    max_concurrent_ws_connections: int = 6

    @field_validator("jwt_secret_key")
    @classmethod
    def _validate_jwt_secret_key_length(cls, value: str) -> str:
        """너무 짧은(추측/무차별대입에 취약한) 시크릿으로 앱이 조용히 뜨는 걸 막는다 -
        HS256 권장 최소 길이(32바이트)에 맞춘 방어선. `openssl rand -hex 32`로
        생성하면 64자가 나와 여유 있게 통과한다."""
        if len(value) < _MIN_JWT_SECRET_KEY_LENGTH:
            raise ValueError(
                f"JWT_SECRET_KEY는 최소 {_MIN_JWT_SECRET_KEY_LENGTH}자 이상이어야 합니다 "
                f"(예: `openssl rand -hex 32`로 생성). 현재 {len(value)}자."
            )
        return value

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        """`logging.basicConfig(level=...)`는 소문자("info")나 오타("INOF")를
        `create_app()`이 호출될 때(테스트마다도 매번!)마다 `ValueError: Unknown
        level: ...`라는 불명확한 예외로 실패시킨다 - 설정 로딩 시점에 미리
        검증해서, 뭐가 문제인지 바로 알 수 있는 메시지로 막는다. 대소문자는
        나머지 설정과 같은 관례(`case_sensitive=False`)로 맞춰 정규화한다."""
        normalized = value.strip().upper()
        if normalized not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"LOG_LEVEL은 {sorted(_VALID_LOG_LEVELS)} 중 하나여야 합니다. "
                f"현재 값: {value!r}"
            )
        return normalized

    @field_validator("environment")
    @classmethod
    def _validate_environment(cls, value: str) -> str:
        """`main.py`는 `settings.environment == "production"`일 때만 /docs,
        /redoc, /openapi.json을 끈다 - 이 비교가 정확히 "production"과만
        일치해야 하므로, `ENVIRONMENT=Production`처럼 대소문자를 틀리거나
        `prod`처럼 줄여 쓰면 조용히 False로 평가되어 실제 프로덕션 배포에서도
        Swagger/ReDoc이 계속 공개로 열려 있게 된다 - 실패가 안전한(fail-closed)
        게 아니라 안전하지 않은(fail-open) 방향으로 조용히 새는 설정이라, 다른
        검증들과 달리 이건 named-값 오타를 반드시 시작 시점에 잡아야 한다.
        대소문자는 정규화하되(관용적인 `Production` 정도는 받아줌), 그 외
        값은 무엇을 의도했는지 알 수 없으므로 거부한다."""
        normalized = value.strip().lower()
        if normalized not in _VALID_ENVIRONMENTS:
            raise ValueError(
                f"ENVIRONMENT은 {sorted(_VALID_ENVIRONMENTS)} 중 하나여야 합니다. "
                f"현재 값: {value!r} (오타가 있으면 프로덕션에서도 Swagger/ReDoc이 "
                f"계속 노출될 수 있어 엄격하게 검증합니다)."
            )
        return normalized

    @field_validator("chat_rate_limit", "auth_rate_limit", "export_rate_limit", "models_rate_limit")
    @classmethod
    def _validate_rate_limit_string(cls, value: str) -> str:
        """`limiter.limit(lambda: get_settings().xxx_rate_limit)`(HTTP)와
        `check_rate_limit()`(WebSocket, `core/rate_limit.py`)가 이 문자열을 각각
        요청마다 파싱하는데, 잘못된 값(예: 사람이 자연스럽게 쓰기 쉬운
        `"10 per minute"`이 아니라 `"10/min"`처럼 지원 안 되는 축약형, 또는
        빈 문자열)이 들어오면 두 경로가 서로 다른, 둘 다 나쁜 방식으로
        실패한다 - HTTP 쪽(slowapi)은 파싱 실패를 조용히 로그만 남기고 그
        요청의 레이트리밋을 그냥 건너뛰어(fail-open) 브루트포스/DoS 방어가
        티도 안 나게 꺼져버리고, WebSocket 쪽(`check_rate_limit`)은 파싱
        예외를 전혀 잡지 않아 학습챗/면접복기 스트리밍이 첫 메시지마다
        처리되지 않은 예외로 죽어버린다(100번 라운드에서 확인한 대로
        WebSocket 스코프에는 전역 예외 핸들러가 적용되지 않음). 두 경로가
        실제로 쓰는 것과 같은 파서(`limits.util.parse_many`, slowapi 내부와
        동일)로 시작 시점에 미리 검증해서, 이 값이 잘못됐다는 걸 요청이
        들어올 때가 아니라 앱이 뜰 때 바로 알 수 있게 한다."""
        try:
            parse_many(value)
        except ValueError as exc:
            raise ValueError(
                f"레이트리밋 문자열이 올바르지 않습니다: {value!r} ({exc}). "
                '"10/minute"처럼 <횟수>/<단위> 형식이어야 합니다.'
            ) from exc
        return value

    @model_validator(mode="after")
    def _validate_quiz_question_count_defaults(self) -> "Settings":
        """`QuizCreateRequest`는 `question_count`를 안 보낸 요청에는
        `default_quiz_question_count`를 그대로 채워 넣을 뿐, 그 값을
        `max_quiz_question_count`와 비교하지 않는다 - 제한 검사는 클라이언트가
        `question_count`를 직접 보낸 경우에만 걸린다. 그래서 운영자가 둘 중
        하나만 바꾸면(예: 비용 절감 위해 MAX만 낮추거나, "더 풍성한 기본값"을
        위해 DEFAULT만 올리면) `question_count`를 생략한 - 아마 대다수인 -
        요청들이 조용히 그 한도를 넘는 문항 수를 요청하게 된다. 요청 시점에
        걸러내는 대신, 다른 검증들처럼 시작 시점에 막아 이 모순된 설정 조합
        자체가 배포되지 못하게 한다.

        아래쪽 한계(1 이상)도 여기서 함께 검증한다 - 요청 스키마 쪽
        `QuizCreateRequest.question_count`는 `Field(ge=1)`로 이미 막혀
        있지만, `question_count`를 생략했을 때 그 자리를 채우는
        `default_quiz_question_count`는 그 검증을 거치지 않는다.
        `DEFAULT_QUIZ_QUESTION_COUNT=0`(혹은 음수)이 설정되면 매번
        "0문항을 만들어달라"는 프롬프트가 나가고, `_GeneratedQuiz.questions`
        가 `min_length=1`이라 항상 검증에 실패해 재시도(`_MAX_QUIZ_
        GENERATION_ATTEMPTS`)까지 다 쓴 뒤 502로 끝난다 - `question_count`를
        생략한 모든 퀴즈 생성 요청이 Ollama 호출만 낭비하고 항상 실패하게
        되므로, 이 조합도 시작 시점에 막는다."""
        if self.default_quiz_question_count < 1:
            raise ValueError(
                f"DEFAULT_QUIZ_QUESTION_COUNT({self.default_quiz_question_count})는 1 이상이어야 합니다."
            )
        if self.default_quiz_question_count > self.max_quiz_question_count:
            raise ValueError(
                "DEFAULT_QUIZ_QUESTION_COUNT"
                f"({self.default_quiz_question_count})는 MAX_QUIZ_QUESTION_COUNT"
                f"({self.max_quiz_question_count})보다 클 수 없습니다."
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
