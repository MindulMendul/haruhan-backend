import time

from prometheus_client import Counter, Gauge, Histogram, generate_latest
from starlette.types import ASGIApp, Message, Receive, Scope, Send

http_requests_total = Counter(
    "haruhan_http_requests_total",
    "처리된 HTTP 요청 수",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "haruhan_http_request_duration_seconds",
    "HTTP 요청 처리 시간(초)",
    ["method", "path"],
)

# 비즈니스 카운터: 회원가입/게스트 전환/퀴즈 생성처럼 제품 지표로 바로 쓸 수 있는 이벤트.
user_signups_total = Counter("haruhan_user_signups_total", "완료된 회원가입 수")
guest_conversions_total = Counter("haruhan_guest_conversions_total", "게스트 -> 실계정 전환 수")
quiz_created_total = Counter("haruhan_quiz_created_total", "생성된 퀴즈 수")

# WebSocket 연결(학습챗/면접복기 스트리밍)은 core/metrics.py의 MetricsMiddleware가
# ASGI "http" scope만 다뤄서(아래 MetricsMiddleware.__call__ 참고) 지금까지 이
# 파일의 어떤 지표에도 전혀 잡히지 않았다 - 99/123/140/164/176라운드가 공들여
# 만든 동시 연결 상한(max_concurrent_ws_connections, DB 커넥션 풀 고갈 방지용
# 안전장치)이 실제로 얼마나 여유가 있는지, 얼마나 자주 거부되는지를 운영자가
# Grafana에서 전혀 볼 수 없었다. dependencies.py의 limit_ws_connections는 두
# 라우트(학습챗/면접복기)가 공유하는 단일 카운터/단일 상한이므로(라우트별로
# 나뉘지 않음), 그 실제 설계를 그대로 반영해 라벨 없이 하나로 합산한다.
ws_active_connections = Gauge(
    "haruhan_ws_active_connections", "현재 활성 WebSocket 연결 수 (학습챗+면접복기 스트리밍 합산)"
)
ws_connections_rejected_total = Counter(
    "haruhan_ws_connections_rejected_total", "동시 연결 상한 초과로 거부된 WebSocket 연결 수"
)


def render_metrics() -> bytes:
    return generate_latest()


class MetricsMiddleware:
    """모든 HTTP 요청의 건수/처리시간을 Prometheus 메트릭으로 기록한다.

    label에는 실제 요청 경로가 아니라 매칭된 라우트 템플릿(예: "/quizzes/{quiz_id}")을
    쓴다 - UUID가 그대로 들어간 실제 경로를 쓰면 호출될 때마다 새 시계열이 생겨
    (cardinality 폭발) Prometheus가 감당할 수 없다. FastAPI가 include_router를 중첩할 때
    상위 라우터(v1_router)의 prefix("/api/v1")는 route.path에 합쳐지지 않고 각 라우터
    자신의 prefix까지만 남는다 - 어차피 UUID만 아니면 되므로 그 정도로 충분하다.
    라우팅이 끝나야 scope["route"]가 채워지므로 self.app() 호출 이후에 읽는다.
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

        duration = time.monotonic() - start
        route = scope.get("route")
        # 매칭 실패(404 등)는 임의의 경로 문자열이 label이 되지 않도록 고정 값으로 묶는다.
        path = route.path if route is not None else "unmatched"
        method = scope.get("method", "")

        http_requests_total.labels(method=method, path=path, status=str(status_code)).inc()
        http_request_duration_seconds.labels(method=method, path=path).observe(duration)
