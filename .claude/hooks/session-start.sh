#!/bin/bash
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# 시스템 파이썬에는 debian이 관리하는 PyJWT 등이 이미 깔려 있어 pip가 충돌한다.
# venv로 격리해서 requirements-dev.txt 버전을 그대로 설치한다.
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --no-cache-dir -r requirements-dev.txt

# 이후 세션 전체에서 pytest/alembic/uvicorn이 이 venv를 쓰도록 PATH를 앞에 건다.
echo "export PATH=\"$CLAUDE_PROJECT_DIR/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"

# JWT_SECRET_KEY는 필수 설정값이라 없으면 앱이 부팅조차 안 된다.
# pytest는 conftest.py에서 자체적으로 채우지만, alembic/uvicorn을 직접
# 돌려볼 때를 위해 개발/테스트 전용 값을 세션에 미리 채워둔다.
echo 'export JWT_SECRET_KEY="dev-only-secret-do-not-use-in-prod-1234567890"' >> "$CLAUDE_ENV_FILE"
