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
from app.core.rate_limit import limiter
from app.core.scheduler import scheduler, setup_scheduler_jobs
from app.repositories.database import close_db_pool, init_db_pool, keep_supabase_alive

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("haruhan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.api_key:
        logger.warning("API_KEY가 설정되지 않아 /api/chat 인증이 비활성화된 상태로 실행됩니다.")

    await init_db_pool(settings.database_url)
    await keep_supabase_alive()

    setup_scheduler_jobs()
    scheduler.start()

    yield

    scheduler.shutdown()
    await close_db_pool()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("처리되지 않은 예외 발생: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


app = create_app()
