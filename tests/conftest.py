import asyncio
import os

# app.core.rate_limit 등 일부 모듈이 임포트 시점에 get_settings()를 호출하므로,
# 다른 임포트보다 먼저 테스트용 필수 설정값을 채워둔다.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only-do-not-use-in-prod")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.db.models  # noqa: F401  (Base.metadata에 테이블을 등록하기 위해 임포트)
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.base import Base
from app.db.session import get_db
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
def db_session_factory():
    """테스트마다 독립적인 인메모리 SQLite DB를 만든다.

    StaticPool을 안 쓰면 커넥션마다 새 인메모리 DB가 생겨(:memory: 기본 동작)
    세션 사이에 테이블/데이터가 공유되지 않는다.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async def _create_all():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_all())

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    yield session_factory

    asyncio.run(engine.dispose())


@pytest.fixture
def client(db_session_factory):
    app = create_app()

    async def _override_get_db():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as test_client:
        yield test_client
