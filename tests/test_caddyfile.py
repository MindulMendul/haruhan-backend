from pathlib import Path

_CADDYFILE_PATH = Path(__file__).resolve().parent.parent / "Caddyfile"


def _read_caddyfile() -> str:
    return _CADDYFILE_PATH.read_text(encoding="utf-8")


def test_caddyfile_enables_response_compression():
    """nginx와 달리 Caddy는 압축을 기본으로 켜주지 않는다 - encode 지시어가
    없으면 학습챗 세션 상세/데이터 export처럼 커질 수 있는 JSON 응답도 전부
    압축 없이 그대로 나간다. 이 지시어가 조용히 빠지는 회귀를 막는다."""
    content = _read_caddyfile()
    assert "encode" in content
    assert "gzip" in content


def test_caddyfile_blocks_public_access_to_metrics():
    """Prometheus는 Caddy를 거치지 않고 내부 docker 네트워크(haruhan-net)로
    haruhan-backend:8000의 /metrics를 직접 스크레이프한다
    (monitoring/prometheus.yml) - Caddy를 통한 공개 노출은 기능적으로
    전혀 필요 없는데, 경로 제한이 없으면 공개 도메인을 통해 누구나
    접근 가능해진다. 이 차단이 조용히 빠지는 회귀를 막는다."""
    content = _read_caddyfile()
    assert "/metrics" in content
    assert "respond 404" in content
