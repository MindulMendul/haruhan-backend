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
