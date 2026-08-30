import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, SignupRequest
from app.schemas.interview_practice import InterviewPracticeCreateRequest
from app.schemas.interview_review import InterviewReviewCreateRequest, InterviewReviewUpdateRequest
from app.schemas.quiz import QuizCreateRequest, QuizUpdateRequest
from app.schemas.study import StudySessionCreateRequest, StudySessionUpdateRequest
from app.schemas.user import GuestUpgradeRequest, UserUpdateRequest
from app.schemas.validators import is_blank


@pytest.mark.parametrize("model_cls", [SignupRequest, LoginRequest])
def test_auth_email_is_lowercased_and_stripped(model_cls):
    request = model_cls(email=" User@Example.COM ", password="supersecret")
    assert request.email == "user@example.com"


def test_guest_upgrade_email_is_normalized():
    request = GuestUpgradeRequest(email="Mixed.Case@Example.com", password="supersecret")
    assert request.email == "mixed.case@example.com"


def test_user_update_email_is_normalized():
    request = UserUpdateRequest(email="New.Email@Example.com", current_password="whatever")
    assert request.email == "new.email@example.com"


def test_user_update_without_email_is_unaffected():
    request = UserUpdateRequest(password="newsecret123", current_password="whatever")
    assert request.email is None


def test_invalid_email_still_rejected():
    with pytest.raises(ValidationError):
        SignupRequest(email="not-an-email", password="supersecret")


# min_length=1은 ""만 막을 뿐 "   " 같은 공백-only 값은 그대로 통과시킨다. 학습챗/
# 퀴즈/면접연습/면접복기 목록에서 사용자에게 그대로 노출되는 라벨 필드(제목/주제/
# 회사명/직무명)에 공백-only 값이 들어가면 목록에서 다른 항목과 구별할 수 없는
# 빈 줄처럼 보이는 항목이 생긴다.
@pytest.mark.parametrize(
    ("model_cls", "kwargs"),
    [
        (StudySessionCreateRequest, {"title": "   "}),
        (StudySessionUpdateRequest, {"title": "   "}),
        (QuizCreateRequest, {"title": "   ", "source_text": "테스트 소스"}),
        (QuizUpdateRequest, {"title": "   "}),
        (InterviewPracticeCreateRequest, {"topic": "   "}),
        (
            InterviewReviewCreateRequest,
            {
                "company": "   ",
                "position": "백엔드",
                "interview_date": "2026-01-01",
                "content": "면접 내용",
            },
        ),
        (
            InterviewReviewCreateRequest,
            {
                "company": "회사명",
                "position": "   ",
                "interview_date": "2026-01-01",
                "content": "면접 내용",
            },
        ),
    ],
)
def test_whitespace_only_label_field_is_rejected(model_cls, kwargs):
    with pytest.raises(ValidationError):
        model_cls(**kwargs)


def test_interview_review_update_allows_omitted_but_rejects_whitespace_only_company():
    with pytest.raises(ValidationError):
        InterviewReviewUpdateRequest(company="   ")

    request = InterviewReviewUpdateRequest(company="회사명")
    assert request.company == "회사명"


# str.strip()은 공백류(str.isspace()가 True인 문자)만 제거하고, zero-width
# space(U+200B)/ZWNJ/ZWJ/word joiner(U+2060)/BOM(U+FEFF)처럼 화면엔 안 보이지만
# 공백이 아닌 유니코드 Cf("서식") 카테고리 문자는 그대로 남긴다 - 그 결과 이런
# 문자로만 이루어진 문자열이 `not value.strip()` 검사를 통과해버렸다(공백류 문자가
# 하나도 없어 strip이 아무것도 제거하지 못함).
@pytest.mark.parametrize(
    "value",
    ["​", "‌", "‍", "⁠", "﻿", "​​​"],
)
def test_is_blank_treats_invisible_format_characters_as_blank(value):
    assert is_blank(value)


def test_is_blank_does_not_treat_visible_content_as_blank():
    assert not is_blank("정상 텍스트")
    assert not is_blank("a​")  # 보이는 문자와 섞여 있으면 공백이 아님


@pytest.mark.parametrize(
    ("model_cls", "kwargs"),
    [
        (StudySessionCreateRequest, {"title": "​​"}),
        (StudySessionUpdateRequest, {"title": "​​"}),
        (QuizCreateRequest, {"title": "​​", "source_text": "테스트 소스"}),
        (QuizUpdateRequest, {"title": "​​"}),
        (InterviewPracticeCreateRequest, {"topic": "​​"}),
        (
            InterviewReviewCreateRequest,
            {
                "company": "​​",
                "position": "백엔드",
                "interview_date": "2026-01-01",
                "content": "면접 내용",
            },
        ),
    ],
)
def test_invisible_only_label_field_is_rejected(model_cls, kwargs):
    """공백만 있는 값을 거부하는 test_whitespace_only_label_field_is_rejected와
    같은 필드들이, 보이는 공백 대신 zero-width space로만 이루어진 값도 똑같이
    거부하는지 확인한다."""
    with pytest.raises(ValidationError):
        model_cls(**kwargs)
