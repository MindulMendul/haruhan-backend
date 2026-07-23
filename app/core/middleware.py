from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


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
        if content_length is not None and int(content_length) > self.max_body_size:
            response = JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
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
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + list(self._HEADERS)
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
