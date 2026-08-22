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
