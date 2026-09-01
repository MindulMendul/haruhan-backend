from datetime import datetime, timezone

from pydantic import BaseModel

from app.schemas.validators import UtcDatetime


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _signup_and_get_token(client, email: str = "utc-datetime@example.com") -> str:
    response = client.post("/api/v1/auth/signup", json={"email": email, "password": "supersecret"})
    assert response.status_code == 201
    return response.json()["access_token"]


class _Model(BaseModel):
    value: UtcDatetime


def test_utc_datetime_appends_z_suffix_to_naive_value():
    """app.core.clock.utcnow_naive()로 저장되는 값과 같은 naive datetime이 들어왔을 때
    직렬화 결과가 "Z"로 끝나는지 확인한다 - 이게 없으면 JS의 new Date(...)가 이 문자열을
    브라우저 로컬 시간으로 오해석한다."""
    dumped = _Model(value=datetime(2026, 8, 21, 12, 0, 0)).model_dump(mode="json")
    assert dumped["value"] == "2026-08-21T12:00:00Z"


def test_utc_datetime_does_not_double_append_z_to_aware_value():
    """이 앱은 항상 naive datetime만 다루지만, tz-aware 값이 들어와도 이미 오프셋
    정보가 있으므로 "Z"를 덧붙이지 않고 그대로 직렬화해야 한다."""
    dumped = _Model(value=datetime(2026, 8, 21, 12, 0, 0, tzinfo=timezone.utc)).model_dump(mode="json")
    assert dumped["value"] == "2026-08-21T12:00:00+00:00"


def test_study_session_response_timestamps_end_with_z(client):
    token = _signup_and_get_token(client)

    create = client.post(
        "/api/v1/study/sessions", json={"title": "OS 프로세스"}, headers=_auth_headers(token)
    )
    assert create.status_code == 201
    body = create.json()

    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")
    # docs/FRONTEND_INTEGRATION.md가 문서화한 그대로 new Date(...)로 파싱 가능해야 한다.
    datetime.fromisoformat(body["created_at"].replace("Z", "+00:00"))


def test_auth_sessions_response_timestamps_end_with_z(client):
    token = _signup_and_get_token(client)

    listing = client.get("/api/v1/auth/sessions", headers=_auth_headers(token))
    assert listing.status_code == 200
    sessions = listing.json()
    assert len(sessions) == 1
    assert sessions[0]["created_at"].endswith("Z")
    assert sessions[0]["expires_at"].endswith("Z")
