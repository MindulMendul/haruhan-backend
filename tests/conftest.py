import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.main import create_app


@pytest.fixture(autouse=True)
def _reset_state():
    """테스트 간 rate limiter 상태와 캐시된 설정을 초기화한다."""
    limiter.reset()
    get_settings.cache_clear()
    yield
    limiter.reset()
    get_settings.cache_clear()


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
