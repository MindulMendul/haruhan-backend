import re
from pathlib import Path

import yaml

_DOCKER_COMPOSE_PATH = Path(__file__).resolve().parent.parent / "docker-compose.yml"
_ENV_EXAMPLE_PATH = Path(__file__).resolve().parent.parent / ".env.example"

# docker-compose.yml 자체(caddy/grafana 서비스)에서만 쓰이고 앱(Settings)은 안
# 읽는 변수 - .env.example의 자체 주석에도 "앱 자체는 이 값을 안 읽음"이라고
# 명시돼 있다. haruhan-backend의 environment: 목록에 없는 게 정상이다.
_COMPOSE_ONLY_VARS = {"DOMAIN", "GRAFANA_ADMIN_PASSWORD"}


def _read_docker_compose() -> str:
    return _DOCKER_COMPOSE_PATH.read_text(encoding="utf-8")


def _parse_docker_compose() -> dict:
    return yaml.safe_load(_read_docker_compose())


def _env_example_variable_names() -> set[str]:
    content = _ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    names = {match.group(1) for match in re.finditer(r"^([A-Z][A-Z0-9_]*)=", content, re.MULTILINE)}
    return names - _COMPOSE_ONLY_VARS


def test_haruhan_backend_receives_environment_variable():
    """main.py는 settings.environment가 정확히 "production"일 때만 /docs, /redoc,
    /openapi.json을 끈다(공격 표면 축소) - .env 파일은 .dockerignore로 빌드
    컨텍스트에서 제외되므로 컨테이너는 이 environment: 목록에 없는 변수를 전혀
    보지 못하고 Settings 기본값("development")으로 조용히 fallback한다. 이
    항목이 없으면 .env에 ENVIRONMENT=production을 아무리 정확히 적어도 실제
    배포 컨테이너에는 전달되지 않아 문서 엔드포인트가 공개 인터넷에 계속
    열려 있게 된다."""
    content = _read_docker_compose()
    assert "ENVIRONMENT=${ENVIRONMENT" in content


def test_haruhan_backend_receives_log_level_variable():
    content = _read_docker_compose()
    assert "LOG_LEVEL=${LOG_LEVEL" in content


def test_every_service_has_log_rotation_configured():
    """Docker의 기본 로깅 드라이버(json-file)는 max-size/max-file을 지정하지
    않으면 로그 파일 크기에 상한이 없다 - uvicorn 기본 access log가 로테이션
    없이 계속 쌓이면 운영 개월 수가 쌓일수록 디스크가 서서히 채워져 결국
    스택 전체가 조용히 멎을 수 있다. 서비스 하나라도 이 설정이 조용히
    빠지는 회귀를 막는다."""
    compose = _parse_docker_compose()
    services = compose["services"]
    assert services  # 최소 하나는 있어야 아래 루프가 의미가 있음
    for name, service in services.items():
        logging_config = service.get("logging")
        assert logging_config is not None, f"{name}에 logging 설정이 없음"
        assert logging_config["driver"] == "json-file"
        assert "max-size" in logging_config["options"]
        assert "max-file" in logging_config["options"]


def test_every_env_example_setting_reaches_haruhan_backend_container():
    """113라운드가 ENVIRONMENT/LOG_LEVEL 두 개가 컨테이너에 전달 안 되던 걸
    고쳤는데, 그 뒤로도 Settings 필드 17개가 더 같은 이유로 빠져 있었다(120
    라운드) - `.env`에 값을 채워도 docker-compose.yml의 haruhan-backend
    `environment:` 목록에 없는 변수는 컨테이너에 전혀 전달되지 않고 코드
    기본값으로 조용히 fallback된다. AUTH_RATE_LIMIT(브루트포스 방어)/
    MAX_BODY_SIZE_BYTES(요청 크기 DoS 방어)/WS_IDLE_TIMEOUT_SECONDS·
    MAX_CONCURRENT_WS_CONNECTIONS(WS DB 커넥션 풀 고갈 방지)처럼 여러
    라운드에 걸쳐 만든 안전장치가 배포 경로에서 죽은 설정이 될 수 있었다.
    앞으로 이 항목들을 하나하나 손으로 대조하는 대신, `.env.example`에
    문서화된 모든 설정이 `docker-compose.yml`의 environment: 목록에도
    전부 있는지 일반화해서 확인한다 - 새 Settings 필드를 추가하면서
    `.env.example`에는 넣고 docker-compose.yml에는 빠뜨리는 이 클래스의
    회귀를 전부 잡는다."""
    compose = _parse_docker_compose()
    env_list = compose["services"]["haruhan-backend"]["environment"]
    compose_var_names = {entry.split("=", 1)[0] for entry in env_list}

    missing = _env_example_variable_names() - compose_var_names
    assert not missing, f"docker-compose.yml에 전달되지 않는 .env.example 설정: {sorted(missing)}"


def test_every_service_has_a_memory_limit():
    """이 호스트는 mindul-net으로 다른 스택(Ollama 포함)과 리소스를 공유한다 -
    서비스 하나가 메모리 누수/버그로 폭주하면 호스트 전체 메모리를 잠식해 같은
    호스트의 다른 스택까지 함께 죽일 수 있다. 튜닝된 상한이 아니라 정상
    사용량보다 훨씬 넉넉한 안전장치(95/99/131라운드와 같은 패턴)라도, 서비스
    하나라도 이 상한이 조용히 빠지는 회귀는 막는다."""
    compose = _parse_docker_compose()
    services = compose["services"]
    assert services
    for name, service in services.items():
        limits = service.get("deploy", {}).get("resources", {}).get("limits", {})
        assert limits.get("memory"), f"{name}에 메모리 상한이 없음"
