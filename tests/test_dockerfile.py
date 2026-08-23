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
