import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_accepts_sufficiently_long_jwt_secret_key():
    settings = Settings(jwt_secret_key="a" * 32)
    assert settings.jwt_secret_key == "a" * 32


def test_settings_rejects_jwt_secret_key_shorter_than_minimum():
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="too-short")
    assert "JWT_SECRET_KEY는 최소 32자 이상이어야 합니다" in str(exc_info.value)


def test_settings_rejects_empty_jwt_secret_key():
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key="")


def test_settings_normalizes_lowercase_log_level():
    """logging.basicConfig(level=...)는 소문자("info")를 받아들이지 않고
    create_app()이 호출될 때마다 ValueError로 앱을 죽인다 - 설정 로딩
    시점에 대문자로 정규화해서 이 문제를 근본적으로 막는다."""
    settings = Settings(jwt_secret_key="a" * 32, log_level="info")
    assert settings.log_level == "INFO"


def test_settings_rejects_invalid_log_level():
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="a" * 32, log_level="INOF")
    assert "LOG_LEVEL은" in str(exc_info.value)


def test_settings_normalizes_mixed_case_environment():
    """main.py는 settings.environment == "production"일 때만 Swagger/ReDoc을
    끄는데, 이 비교가 정확히 일치해야 하므로 "Production"처럼 대소문자가
    다르면 조용히 False가 되어 프로덕션에서도 문서가 계속 열려 있게 된다 -
    관용적으로 흔히 쓰는 대소문자 변형은 정규화해서 받아준다."""
    settings = Settings(jwt_secret_key="a" * 32, environment="Production")
    assert settings.environment == "production"


def test_settings_rejects_invalid_environment():
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="a" * 32, environment="prod")
    assert "ENVIRONMENT은" in str(exc_info.value)


def test_settings_accepts_default_quiz_question_count_equal_to_max():
    settings = Settings(
        jwt_secret_key="a" * 32, default_quiz_question_count=5, max_quiz_question_count=5
    )
    assert settings.default_quiz_question_count == 5


def test_settings_rejects_default_quiz_question_count_over_max():
    """QuizCreateRequest는 question_count를 안 보낸 요청에만
    default_quiz_question_count를 그대로 채워 넣고, 그 값을
    max_quiz_question_count와 비교하지 않는다 - 운영자가 둘 중 하나만
    바꾸면(예: 비용 절감 위해 MAX만 낮춤) question_count를 생략한 요청들이
    조용히 그 한도를 넘는 문항 수를 요청하게 된다. 이 모순된 조합을 요청
    시점이 아니라 설정 로딩 시점에 막는다."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="a" * 32, default_quiz_question_count=20, max_quiz_question_count=10)
    assert "DEFAULT_QUIZ_QUESTION_COUNT" in str(exc_info.value)
    assert "MAX_QUIZ_QUESTION_COUNT" in str(exc_info.value)


@pytest.mark.parametrize("bad_value", [0, -1])
def test_settings_rejects_default_quiz_question_count_below_one(bad_value):
    """요청 스키마의 `QuizCreateRequest.question_count`는 `Field(ge=1)`로 이미
    막혀 있지만, `question_count`를 생략했을 때 그 자리를 채우는
    `default_quiz_question_count`는 그 검증을 거치지 않는다.
    `DEFAULT_QUIZ_QUESTION_COUNT=0`(또는 음수)이면 `question_count`를 생략한
    모든 퀴즈 생성 요청이 "0문항을 만들어달라"는 프롬프트를 보내 매번 검증
    실패 -> 재시도 -> 502로 끝나게 된다 - 이 조합도 설정 로딩 시점에 막는다."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="a" * 32, default_quiz_question_count=bad_value)
    assert "DEFAULT_QUIZ_QUESTION_COUNT" in str(exc_info.value)


@pytest.mark.parametrize("field", ["chat_rate_limit", "auth_rate_limit", "export_rate_limit"])
def test_settings_accepts_well_formed_rate_limit_string(field):
    settings = Settings(jwt_secret_key="a" * 32, **{field: "3/minute"})
    assert getattr(settings, field) == "3/minute"


@pytest.mark.parametrize("field", ["chat_rate_limit", "auth_rate_limit", "export_rate_limit"])
@pytest.mark.parametrize("bad_value", ["10/min", "", "10", "bogus-rate-limit"])
def test_settings_rejects_malformed_rate_limit_string(field, bad_value):
    """`@limiter.limit(lambda: get_settings().xxx_rate_limit)`(HTTP)는 이 문자열
    파싱이 실패하면 조용히 로그만 남기고 레이트리밋 자체를 건너뛰어(fail-open)
    브루트포스/DoS 방어가 티도 안 나게 꺼져버리고, `check_rate_limit()`
    (WebSocket, `core/rate_limit.py`)은 파싱 예외를 전혀 안 잡아서 학습챗/
    면접복기 스트리밍이 첫 메시지마다 처리되지 않은 예외로 죽어버린다 - "10/min"
    같은 자연스러운 오타나 빈 문자열이 두 경로 모두에서 실제로 파싱에 실패하는
    값임을 확인하고, Settings가 이걸 시작 시점에 미리 거부하는지 확인한다."""
    with pytest.raises(ValidationError):
        Settings(jwt_secret_key="a" * 32, **{field: bad_value})


@pytest.mark.parametrize("field", ["access_token_expire_minutes", "refresh_token_expire_days"])
def test_settings_accepts_positive_token_expiry(field):
    settings = Settings(jwt_secret_key="a" * 32, **{field: 1})
    assert getattr(settings, field) == 1


@pytest.mark.parametrize("field", ["access_token_expire_minutes", "refresh_token_expire_days"])
@pytest.mark.parametrize("bad_value", [0, -1])
def test_settings_rejects_non_positive_token_expiry(field, bad_value):
    """core/tokens.py의 create_access_token()/refresh_token_expiry()는 이 값을
    그대로 `now + value * 단위`로 만료 시각 계산에 쓴다 - 0이나 음수가 들어오면
    발급되는 토큰이 태어날 때부터 이미 만료된 상태가 된다. Settings() 생성
    자체는 성공해 앱도 정상적으로 뜨므로, 로그인/회원가입은 겉보기엔 멀쩡히
    200을 반환하면서 발급한 토큰만 곧바로 무효가 되는, 시작 시점에는 전혀 티가
    안 나는 전면적인 인증 장애로 이어진다."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="a" * 32, **{field: bad_value})
    assert field.upper() in str(exc_info.value)


def test_settings_accepts_max_quiz_choice_count_of_four_or_more():
    settings = Settings(jwt_secret_key="a" * 32, max_quiz_choice_count=4)
    assert settings.max_quiz_choice_count == 4


@pytest.mark.parametrize("bad_value", [0, 1, 2, 3])
def test_settings_rejects_max_quiz_choice_count_below_four(bad_value):
    """quiz_service.py의 _build_quiz_prompt()는 MAX_QUIZ_CHOICE_COUNT와 무관하게
    모델에게 항상 "각 문항은 4개의 보기를 가지고"라고 고정으로 요청한다 - 정상
    동작하는 모델은 매번 보기 4개를 뱉는다는 뜻이다. MAX_QUIZ_CHOICE_COUNT를
    4 미만으로 설정하면, 모델이 시키는 대로 4개를 뱉을 때마다 검증(len(choices)
    <= max_quiz_choice_count)에 매번 걸려 재시도까지 전부 소진하고 502로
    끝난다 - 퀴즈 생성 기능 전체가 시작 시점에는 전혀 티가 안 나는 상태로
    계속 실패하게 된다."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="a" * 32, max_quiz_choice_count=bad_value)
    assert "MAX_QUIZ_CHOICE_COUNT" in str(exc_info.value)


def test_settings_accepts_positive_max_prompt_length():
    settings = Settings(jwt_secret_key="a" * 32, max_prompt_length=1)
    assert settings.max_prompt_length == 1


@pytest.mark.parametrize("bad_value", [0, -1])
def test_settings_rejects_non_positive_max_prompt_length(bad_value):
    """ChatRequest/StudyMessageCreateRequest/InterviewPracticeAnswerRequest의
    길이 검증과 routes/study.py의 WS 스트리밍 경로가 전부 이 값을
    len(value) > max_length로 검사한다. 0 이하면 min_length=1을 통과한(=빈
    문자열이 아닌) 어떤 메시지든 항상 이 조건을 만족해 거부되어, 학습챗/
    면접연습/일반 채팅 등 메시지를 보내는 기능 전체가 시작 시점에는 전혀
    티가 안 나는 상태로 계속 막히게 된다."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="a" * 32, max_prompt_length=bad_value)
    assert "MAX_PROMPT_LENGTH" in str(exc_info.value)


def test_settings_accepts_positive_max_body_size_bytes():
    settings = Settings(jwt_secret_key="a" * 32, max_body_size_bytes=1)
    assert settings.max_body_size_bytes == 1


@pytest.mark.parametrize("bad_value", [0, -1])
def test_settings_rejects_non_positive_max_body_size_bytes(bad_value):
    """MaxBodySizeMiddleware(core/middleware.py)는 Content-Length 헤더가 있는
    모든 요청에 대해 parsed_content_length > max_body_size면 413로 거부한다.
    0 이하면 본문이 있는 요청은 전부 거부되고, 음수면 본문이 없는(Content-
    Length: 0) 요청까지도 거부되어 회원가입/로그인/학습챗/퀴즈 제출 등
    쓰기 API 사실상 전체가 시작 시점에는 전혀 티가 안 나는 상태로 계속
    막히게 된다."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret_key="a" * 32, max_body_size_bytes=bad_value)
    assert "MAX_BODY_SIZE_BYTES" in str(exc_info.value)
