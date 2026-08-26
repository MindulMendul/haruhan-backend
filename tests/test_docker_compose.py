from pathlib import Path

_DOCKER_COMPOSE_PATH = Path(__file__).resolve().parent.parent / "docker-compose.yml"


def _read_docker_compose() -> str:
    return _DOCKER_COMPOSE_PATH.read_text(encoding="utf-8")


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
