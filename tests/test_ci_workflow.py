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


def test_ci_type_checks_scripts_directory():
    """119번 라운드가 scripts/backfill_knowledge_chunks.py에 새 의존성(PyYAML)을
    추가하면서 "앞으로 CI와 정확히 같은 mypy app tests scripts를 로컬에서도
    돌린다"는 검증 습관을 로그에 남겼는데, 정작 CI 워크플로 자체는
    `mypy app tests`만 실행해 scripts/ 디렉터리를 한 번도 타입 체크한 적이
    없었다 - scripts/의 타입 회귀는 로컬에서 그 습관을 안 지키면 CI를 그대로
    통과해 머지될 수 있는 사각지대였다."""
    content = _read_ci_workflow()
    assert "mypy app tests scripts" in content
