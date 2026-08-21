#!/usr/bin/env python3
"""PostToolUse 훅: app/ 코드를 편집하면 관련 테스트를 바로 돌려서 피드백을 준다.

Edit/Write 대상 파일 이름에서 관련 tests/test_*.py를 추론해 그것만 실행한다.
연관 테스트를 특정하지 못하면(core/공유 파일 등) 전체 스위트를 돌린다 (느리더라도
놓치는 것보다 낫다). 실패하면 exit code 2로 종료해 실패 내용을 Claude에게 그대로
돌려준다 (Claude Code PostToolUse 훅에서 stderr를 피드백으로 전달하는 컨벤션).
"""
import json
import os
import shutil
import subprocess
import sys

REPO_ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
WATCHED_PREFIXES = ("app/", "tests/", "scripts/")
STRIP_SUFFIXES = ("_service", "_repository")
STOPWORDS = {"service", "repository", "model"}


def _read_input() -> dict:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def _target_file(payload: dict) -> str | None:
    tool_input = payload.get("tool_input") or {}
    return tool_input.get("file_path")


def _relevant_test_files(rel_path: str) -> list[str]:
    tests_dir = os.path.join(REPO_ROOT, "tests")
    if not os.path.isdir(tests_dir):
        return []

    stem = os.path.splitext(os.path.basename(rel_path))[0]
    for suffix in STRIP_SUFFIXES:
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    tokens = {t for t in stem.split("_") if t and t not in STOPWORDS}

    matches = []
    for name in sorted(os.listdir(tests_dir)):
        if not (name.startswith("test_") and name.endswith(".py")):
            continue
        test_stem = name[len("test_") : -len(".py")]
        test_tokens = {t for t in test_stem.split("_") if t}
        if (
            test_stem == stem
            or stem in test_stem
            or test_stem in stem
            or (tokens & test_tokens)
        ):
            matches.append(os.path.join("tests", name))
    return matches


def main() -> int:
    payload = _read_input()
    file_path = _target_file(payload)
    if not file_path:
        return 0

    try:
        rel_path = os.path.relpath(file_path, REPO_ROOT)
    except ValueError:
        return 0

    if rel_path.startswith("..") or not rel_path.endswith(".py"):
        return 0
    if not rel_path.startswith(WATCHED_PREFIXES):
        return 0

    # PostToolUse 훅 프로세스는 세션 셸의 PATH($CLAUDE_ENV_FILE로 얹은 .venv/bin 포함)를
    # 물려받지 않는다. shutil.which만 쓰면 PATH에 먼저 걸리는 다른(의존성 없는) pytest를
    # 집어서 fastapi ModuleNotFoundError가 난다 - 프로젝트 venv를 명시적으로 먼저 본다.
    venv_pytest = os.path.join(REPO_ROOT, ".venv", "bin", "pytest")
    pytest_bin = venv_pytest if os.path.isfile(venv_pytest) else shutil.which("pytest")
    if pytest_bin is None:
        # venv가 아직 없거나(세션 시작 훅 미실행) pytest가 없는 환경에서는 조용히 넘어간다.
        return 0

    if rel_path.startswith("tests/") and os.path.isfile(os.path.join(REPO_ROOT, rel_path)):
        targets = [rel_path]
    else:
        targets = _relevant_test_files(rel_path)

    args = [pytest_bin, "-q", *targets]
    scope = ", ".join(targets) if targets else "전체 스위트 (연관 테스트를 특정하지 못함)"

    try:
        result = subprocess.run(
            args, cwd=REPO_ROOT, capture_output=True, text=True, timeout=120
        )
    except subprocess.TimeoutExpired:
        print(
            f"[post-edit-test] 테스트 실행이 120초를 넘겨 중단했습니다 ({scope}).",
            file=sys.stderr,
        )
        return 2

    if result.returncode != 0:
        print(f"[post-edit-test] {rel_path} 편집 후 테스트 실패 ({scope}):", file=sys.stderr)
        print(result.stdout[-4000:], file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
        return 2

    print(f"[post-edit-test] {rel_path} 관련 테스트 통과 ({scope}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
