from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST

from app.core.metrics import render_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def get_metrics() -> Response:
    """Prometheus가 스크레이프할 엔드포인트. 인증 없이 노출한다 (Prometheus 표준 관례)."""
    return Response(content=render_metrics(), media_type=CONTENT_TYPE_LATEST)
