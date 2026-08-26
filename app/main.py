import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import (
    http_exception_handler,
    rate_limit_exceeded_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging
from app.core.metrics import MetricsMiddleware
from app.core.middleware import AccessLogMiddleware, MaxBodySizeMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.core.scheduler import scheduler, setup_scheduler_jobs
from app.db.session import close_engine, init_engine, keep_supabase_alive

logger = logging.getLogger("haruhan")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # type: ignore[arg-type]
    # 모든 HTTPException/검증 오류를 {"error": {"code", "message"}} 형태로 통일한다 -
    # 프론트가 에러 종류를 한글 메시지 문자열 매칭이 아니라 code로 분기할 수 있게.
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]

    # 라우터 바로 앞(FastAPI 라우팅/예외 핸들러보다는 바깥이지만 CORS/보안 헤더
    # 미들웨어보다는 안쪽)에 등록한다. add_middleware는 나중에 등록할수록 더
    # 바깥쪽으로 감싸므로, 여기서 가장 먼저 등록해야 CORSMiddleware/
    # SecurityHeadersMiddleware가 이 미들웨어를 감싸는 형태가 된다.
    # Content-Length만 보고 본문을 읽기 전에 차단한다는 목적(라우터/엔드포인트가
    # 실제로 본문을 읽기 전에 막는 것)에는 이 위치로도 변화가 없다 - 본문을
    # 읽는 건 여전히 이보다 안쪽인 라우터/엔드포인트뿐이기 때문이다. 반대로
    # 예전처럼 CORS/보안 헤더 미들웨어보다 바깥에 두면, 이 미들웨어가 413을
    # 직접 응답해버리는 요청은 그 두 미들웨어를 아예 거치지 않아
    # Access-Control-Allow-Origin이나 X-Content-Type-Options 같은 헤더가 전혀
    # 안 붙는 채로 나갔다 - 실제로 Origin 헤더를 넣어 대용량 payload를
    # cross-origin 요청으로 보내 재현 확인(이 프로젝트의 실제 배포 형태가
    # Vercel 프론트 → 다른 도메인 API인 cross-origin 구조라 61번 항목이
    # expose_headers를 고친 것과 같은 이유로 실제 영향이 있다). 브라우저는
    # CORS 헤더가 없는 응답을 자바스크립트에서 읽지 못하게 막으므로, 사용자는
    # "메시지가 너무 깁니다" 같은 실제 에러 대신 그냥 알 수 없는 네트워크
    # 오류만 보게 된다.
    app.add_middleware(MaxBodySizeMiddleware, max_body_size=settings.max_body_size_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
        # 브라우저는 "CORS-safelisted" 응답 헤더(Content-Type 등 극히 일부)만
        # 기본으로 JS에 노출하고, 그 외는 서버가 명시적으로 허용해야 fetch()의
        # response.headers.get(...)으로 읽을 수 있다. 이 목록이 없으면
        # FRONTEND_INTEGRATION.md가 프론트에게 직접 읽으라고 안내하는
        # X-Total-Count(페이지네이션)/X-RateLimit-*·Retry-After(레이트리밋)가
        # cross-origin 프론트(예: Vercel에 배포된 프론트가 다른 도메인의 이
        # API를 호출하는 이 프로젝트의 실제 배포 형태)에서는 응답에 실려
        # 와도 JS로는 안 보이는 상태였다.
        expose_headers=[
            "X-Total-Count",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "Retry-After",
        ],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    # 응답 헤더/본문 크기 검사까지 포함한 전체 왕복 시간을 재기 위해 가장 바깥쪽에 둔다.
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(MetricsMiddleware)

    app.include_router(api_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("처리되지 않은 예외 발생: %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Internal server error"}},
        )

    return app


app = create_app()
