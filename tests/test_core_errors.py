from app.core.errors import build_error_body


def test_build_error_body_wraps_plain_string_with_default_code():
    assert build_error_body(404, "Quiz not found") == {
        "error": {"code": "not_found", "message": "Quiz not found"}
    }


def test_build_error_body_keeps_explicit_structured_detail():
    detail = {"code": "invalid_credentials", "message": "Invalid email or password"}
    assert build_error_body(401, detail) == {"error": detail}


def test_build_error_body_falls_back_to_generic_code_for_unknown_status():
    assert build_error_body(418, "teapot") == {
        "error": {"code": "http_418", "message": "teapot"}
    }


def test_build_error_body_ignores_dict_detail_missing_required_keys():
    # code나 message 중 하나라도 빠지면 구조화된 detail로 취급하지 않고
    # 문자열로 변환해서 기본 code를 붙인다.
    detail = {"code": "only_code"}
    result = build_error_body(400, detail)
    assert result["error"]["code"] == "bad_request"
    assert "only_code" in result["error"]["message"]
