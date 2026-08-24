from pathlib import Path

_DOCKERIGNORE_PATH = Path(__file__).resolve().parent.parent / ".dockerignore"


def _read_dockerignore() -> str:
    return _DOCKERIGNORE_PATH.read_text(encoding="utf-8")


def test_dockerignore_excludes_actual_venv_directory_name():
    """이 프로젝트의 실제 가상환경 디렉터리명은 .venv(점 포함)인데, 예전에는
    venv/만 제외 목록에 있었다 - docker build/docker-compose build를 실행할
    때마다 .venv/(수백 MB)가 빌드 컨텍스트로 그대로 전송되고 있었다. 정확한
    디렉터리명이 제외 목록에서 조용히 빠지는 회귀를 막는다."""
    content = _read_dockerignore()
    assert ".venv/" in content


def test_dockerignore_excludes_bulky_dev_only_caches():
    """.mypy_cache/(수십~수백 MB)와 .pytest_cache/도 이미지에는 전혀 필요 없는
    로컬 전용 캐시인데 제외 목록에 없었다 - 같은 이유(빌드 컨텍스트 전송 비용)로
    함께 제외해야 한다."""
    content = _read_dockerignore()
    assert ".mypy_cache/" in content
    assert ".pytest_cache/" in content
