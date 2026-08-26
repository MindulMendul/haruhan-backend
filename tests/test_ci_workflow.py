from pathlib import Path

_CI_WORKFLOW_PATH = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"


def _read_ci_workflow() -> str:
    return _CI_WORKFLOW_PATH.read_text(encoding="utf-8")


def test_ci_validates_docker_compose_and_caddyfile():
    """113/114라운드가 docker-compose.yml/Caddyfile에서 실제 배포 사고를 찾아
    고쳤는데, 정작 CI의 test/migrations job은 app/과 migrations/만 다루고
    배포 파일은 사람이 리뷰할 때만 걸러지고 있었다 - docker compose config
    (YAML/스키마 구조, 필수 변수 채움 여부)와 caddy validate(Caddyfile 문법)
    검증 스텝이 조용히 빠지는 회귀를 막는다."""
    content = _read_ci_workflow()
    assert "docker compose config" in content
    assert "caddy validate" in content
