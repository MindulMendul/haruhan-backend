import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import AccessLogMiddleware, MaxBodySizeMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.core.scheduler import scheduler, setup_scheduler_jobs
from app.db.session import close_engine, init_engine, keep_supabase_alive

logger = logging.getLogger("haruhan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if not settings.api_key:
        logger.warning("API_KEY가 설정되지 않아 /api/chat 인증이 비활성화된 상태로 실행됩니다.")

    await init_engine(settings.database_url)
    await keep_supabase_alive()

    setup_scheduler_jobs()
    scheduler.start()

    yield

    scheduler.shutdown()
    await close_engine()


def create_app() -> FastAPI:
    # 매 호출 시점의 설정을 읽는다 (테스트에서 env를 바꾸고 재생성하는 시나리오 포함).
    settings = get_settings()
    configure_logging(settings.log_level)

    # 프로덕션에서는 Swagger/ReDoc(유일하게 실제 HTML을 서빙하는 지점)을 꺼서 공격 표면을 줄인다.
    is_production = settings.environment == "production"

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    app.state.limiter = limiter
    # slowapi 핸들러 시그니처가 starlette의 범용 예외 핸들러 타입보다 좁게 잡혀 있어
    # 생기는 오탐이다 (slowapi/starlette 생태계에서 흔히 쓰이는 정상 패턴).
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    # 가장 바깥쪽(가장 나중에 add된 미들웨어)에서 본문을 읽기 전에 크기부터 차단한다.
    app.add_middleware(MaxBodySizeMiddleware, max_body_size=settings.max_body_size_bytes)
    # 응답 헤더/본문 크기 검사까지 포함한 전체 왕복 시간을 재기 위해 가장 바깥쪽에 둔다.
    app.add_middleware(AccessLogMiddleware)

    app.include_router(api_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("처리되지 않은 예외 발생: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


app = create_app()
