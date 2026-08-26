from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

# status code별 기본 code. 라우트/서비스가 아직 구체적인 code를 안 붙인
# HTTPException(detail이 그냥 문자열인 경우)에 대한 폴백이다.
_DEFAULT_CODES_BY_STATUS = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_413_CONTENT_TOO_LARGE: "payload_too_large",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
    status.HTTP_502_BAD_GATEWAY: "bad_gateway",
    status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
}


def build_error_body(status_code: int, detail: object) -> dict:
    """HTTPException.detail을 {"error": {"code", "message"}} 형태로 통일한다.

    detail이 이미 {"code": ..., "message": ...} 형태의 dict면(개별 서비스가 구체적인
    code를 명시적으로 붙인 경우) 그대로 쓴다. 아직 대부분의 raise 지점은 문자열
    detail만 넘기므로(점진적으로 code를 붙여나가는 중), 그 경우 상태 코드 기반
    기본 code로 채운다 - 그래도 프론트는 최소한 code 필드로 에러 종류를 분기할 수
    있다.
    """
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return {"error": detail}
    code = _DEFAULT_CODES_BY_STATUS.get(status_code, f"http_{status_code}")
    return {"error": {"code": code, "message": str(detail)}}


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_body(exc.status_code, exc.detail),
        headers=exc.headers,
    )


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """slowapi 기본 핸들러(`{"error": "Rate limit exceeded: ..."}`, 문자열)를
    나머지 에러 응답과 같은 `{"error": {"code", "message"}}` 형태로 통일한다.

    Retry-After/X-RateLimit-* 헤더는 slowapi의 Limiter._inject_headers가
    request.state.view_rate_limit(라우트를 처리하며 slowapi가 채워둔 것)을 보고
    붙여준다 - 기본 핸들러와 동일하게 그대로 재사용한다.
    """
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": {"code": "rate_limited", "message": f"Rate limit exceeded: {exc.detail}"}},
    )
    return request.app.state.limiter._inject_headers(response, request.state.view_rate_limit)


def sanitize_pydantic_errors(errors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """pydantic 에러 목록(ValidationError.errors()/RequestValidationError.errors())의
    각 항목에는 검증에 실패한 필드에 실제로 들어온 원본 값이 "input"으로 그대로
    담겨 있다 - password/current_password/refresh_token처럼 민감한 필드가 길이
    제한 등으로 검증에 실패하면, 평문 값이 응답 바디에 그대로 실려서 브라우저
    devtools 히스토리나 API 로깅/모니터링 도구(Sentry 등) 어디에나 남을 수
    있었다. 필드 위치(loc)/에러 종류(type)/메시지(msg)에는 input이 필요 없으므로
    제거한다."""
    return [{key: value for key, value in error.items() if key != "input"} for error in errors]


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    sanitized_errors = sanitize_pydantic_errors(exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=jsonable_encoder(
            {
                "error": {
                    "code": "validation_error",
                    "message": "요청 값이 올바르지 않습니다.",
                    "details": sanitized_errors,
                }
            }
        ),
    )
