from pathlib import Path

_DOCKERFILE_PATH = Path(__file__).resolve().parent.parent / "Dockerfile"


def _read_dockerfile() -> str:
    return _DOCKERFILE_PATH.read_text(encoding="utf-8")


def test_uvicorn_trusts_proxy_headers():
    """docker-compose 구성상 이 컨테이너는 포트를 호스트에 노출하지 않고 Caddy
    리버스 프록시를 통해서만 트래픽을 받는다. --proxy-headers 없이는 uvicorn이
    X-Forwarded-For를 무시해서 모든 요청의 request.client.host가 Caddy
    컨테이너 IP로 찍히고, 그 결과 IP 기준 레이트리밋(auth_rate_limit/
    chat_rate_limit)이 전체 사용자가 하나의 버킷을 공유하는 것과 같아져
    버린다. 이 플래그가 CMD에서 조용히 빠지는 회귀를 막는다."""
    content = _read_dockerfile()
    assert "--proxy-headers" in content
    assert "--forwarded-allow-ips" in content


def test_uvicorn_websocket_message_size_matches_http_body_limit():
    """HTTP는 MaxBodySizeMiddleware(기본 1MiB)로 요청 본문 크기를 막지만,
    WebSocket 경로(study/interview-review 스트리밍)는 이 미들웨어를 안 거치고
    uvicorn 기본값(16MiB)을 그대로 썼다 - 아무도 의도적으로 정한 적 없는
    값이라 WS 쪽만 유독 대용량 메시지에 취약했다(직접 uvicorn 서버를 띄워
    기본값으로는 2MiB 메시지가 그대로 통과하고, --ws-max-size를 켜면
    프로토콜 레벨에서 거부되는 것을 재현 확인함). HTTP 쪽 기본값과 같은
    1MiB로 맞추는 이 플래그가 CMD에서 조용히 빠지는 회귀를 막는다."""
    content = _read_dockerfile()
    assert "--ws-max-size=1048576" in content


def _cmd_line(content: str) -> str:
    lines = [line for line in content.splitlines() if line.startswith("CMD ")]
    assert len(lines) == 1
    return lines[0]


def test_uvicorn_log_level_is_lowered_to_avoid_leaking_ws_auth_tokens_in_logs():
    """학습챗/면접복기 WebSocket 인증은 브라우저가 커스텀 헤더를 못 보내서 access
    token을 쿼리 파라미터(?token=<access_token>)로 받는다(get_current_user_ws,
    core/dependencies.py) - 문서화된 정상 계약이다. uvicorn 기본(info) 로그
    레벨에서는 이 핸드셰이크마다 uvicorn.error 로거(핸드셰이크 자체를 다루는
    websockets_sansio_impl.py가 씀 - haruhan.access와는 완전히 별개 경로라
    173라운드의 AccessLogMiddleware/WS 접근 로그로는 못 막음)가 실제 JWT가
    그대로 담긴 쿼리 문자열을 `"WebSocket /.../stream?token=<JWT>" [accepted]`
    형태로 stdout에 남겨, docker-compose.yml의 json-file 로그(141라운드)에
    최대 access_token_expire_minutes(기본 30분)간 유효한 토큰이 평문으로 쌓인다.
    직접 uvicorn을 띄워 실제 JWT가 이 로그 줄에 찍히는 것과, --no-access-log
    (uvicorn.access 로거만 끔)는 다른 로거라서 이 줄에 전혀 영향이 없지만
    --log-level warning으로 올리면 이 INFO 레벨 로그가 사라지는 것까지 재현
    확인했다. 이 플래그가 CMD에서 조용히 빠지는(혹은 info로 되돌아가는)
    회귀를 막는다."""
    cmd_line = _cmd_line(_read_dockerfile())
    assert "--log-level" in cmd_line
    assert "warning" in cmd_line
