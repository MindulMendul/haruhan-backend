import logging
import time

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.core.errors import build_error_body
from app.core.tokens import decode_access_token

access_logger = logging.getLogger("haruhan.access")


class MaxBodySizeMiddleware:
    """Content-Length가 제한을 넘는 요청을 본문을 읽기 전에 차단한다.

    Content-Length 헤더가 없는 chunked 요청까지는 막지 못하지만,
    가장 흔한 대용량 payload를 통한 메모리 소모형 DoS를 저비용으로 방지한다.
    """

    def __init__(self, app: ASGIApp, max_body_size: int) -> None:
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        content_length = headers.get(b"content-length")
        parsed_content_length: int | None = None
        if content_length is not None:
            try:
                parsed_content_length = int(content_length)
            except ValueError:
                # 헤더 자체가 숫자가 아니면(오타, 스캐너/프록시의 이상한 값 등)
                # 크기를 알 수 없는 것으로 취급한다 - chunked 요청처럼 이
                # 미들웨어가 애초에 못 막는 경우와 같은 취급이다. 그냥
                # int()를 부르면 처리되지 않은 ValueError가 이 미들웨어
                # (ASGI 계층, FastAPI 라우팅/예외 핸들러보다 바깥)를 뚫고 나가
                # main.py의 전역 핸들러까지 올라가 방어 목적의 미들웨어 자체가
                # 아무 malformed 헤더에나 500을 만들어내는 원인이 됐다.
                parsed_content_length = None

        if parsed_content_length is not None and parsed_content_length > self.max_body_size:
            # 이 미들웨어는 FastAPI 라우팅/예외 핸들러 바깥(ASGI 계층)에서 직접
            # 응답을 만들기 때문에, app.core.errors의 HTTPException 핸들러를
            # 거치지 않는다 - 그래서 나머지 모든 에러와 같은 {"error": {"code",
            # "message"}} 포맷이 되도록 build_error_body를 직접 재사용한다.
            response = JSONResponse(
                status_code=413,
                content=build_error_body(413, "Request body too large"),
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


class SecurityHeadersMiddleware:
    """모든 응답에 기본적인 브라우저 보안 헤더를 붙인다.

    이 API는 쿠키가 아닌 Bearer 토큰으로 인증하고 CORS도 credential을 안 쓰므로
    CSRF는 구조적으로 해당하지 않는다. 여기서 다루는 건 그와 별개로,
    브라우저가 응답을 잘못 해석/렌더링하지 못하도록 막는 표준 헤더들이다.
    """

    _HEADERS = (
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        # 브라우저는 이 헤더를 HTTPS 응답에서만 실제로 적용한다(스펙상 평문 HTTP
        # 응답에 실려 와도 무시함) - 로컬 http 개발 환경에 영향 없이 항상 붙여도
        # 안전하다. 운영은 Caddy 뒤에서 HTTPS로만 서빙되므로(0. 준비 사항 참고)
        # 프로토콜 다운그레이드/쿠키 가로채기류 공격에 대한 표준 방어선이 된다.
        (b"strict-transport-security", b"max-age=63072000; includeSubDomains"),
        # Bearer 토큰 인증이라 브라우저 기본 캐시 정책이 어느 정도 안전망 역할을
        # 하지만, /export/me처럼 계정 전체 이력(학습챗 내용, 퀴즈 정답, 면접 복기
        # 원문)을 한 번에 반환하는 엔드포인트를 포함해 모든 응답에 명시적인
        # no-store가 없으면 공유 컴퓨터의 브라우저 디스크 캐시나 back-forward
        # cache, 향후 캐싱 프록시가 앞단에 추가될 경우의 사고 가능성이 남는다.
        # 정적 자산을 서빙하지 않는 순수 API 서버라 모든 응답에 일괄 적용해도
        # 안전하다.
        (b"cache-control", b"no-store"),
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + list(self._HEADERS)
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


def _extract_user_id(scope: Scope) -> str | None:
    """Authorization 헤더에서 best-effort로 user_id(JWT sub)를 뽑는다.

    로깅용 부가 정보일 뿐이라, 토큰이 없거나 만료/위조됐어도 요청 자체를 막으면
    안 된다 - 어떤 이유로 실패하든 조용히 None을 반환한다.
    """
    headers = dict(scope.get("headers") or [])
    auth_header = headers.get(b"authorization")
    if not auth_header:
        return None
    try:
        scheme, _, token = auth_header.decode("latin-1").partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None
        payload = decode_access_token(token, get_settings())
        return payload.get("sub")
    except Exception:
        return None


class AccessLogMiddleware:
    """모든 HTTP 요청을 한 줄짜리 구조화된 로그(key=value)로 남긴다.

    처리되지 않은 예외는 main.py의 전역 핸들러가 이미 스택트레이스까지 로깅하므로,
    이 미들웨어는 성공 요청을 포함한 전체 트래픽의 최소 정보(누가/언제/얼마나
    걸렸는지)를 남기는 역할이다. 응답 헤더나 본문 크기 검사까지 포함한 전체 왕복
    시간을 재려고 가장 바깥쪽 미들웨어로 등록해서 쓴다.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.monotonic()
        status_code = 0

        async def send_and_capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_and_capture_status)

        duration_ms = (time.monotonic() - start) * 1000
        client = scope.get("client")
        access_logger.info(
            "method=%s path=%s status=%s duration_ms=%.1f client=%s user_id=%s",
            scope.get("method", ""),
            scope.get("path", ""),
            status_code,
            duration_ms,
            client[0] if client else "-",
            _extract_user_id(scope) or "-",
        )
