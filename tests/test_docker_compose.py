from pathlib import Path

import yaml

_DOCKER_COMPOSE_PATH = Path(__file__).resolve().parent.parent / "docker-compose.yml"


def _read_docker_compose() -> str:
    return _DOCKER_COMPOSE_PATH.read_text(encoding="utf-8")


def _parse_docker_compose() -> dict:
    return yaml.safe_load(_read_docker_compose())


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
