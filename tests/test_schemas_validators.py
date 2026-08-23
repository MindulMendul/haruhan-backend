import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, SignupRequest
from app.schemas.user import GuestUpgradeRequest, UserUpdateRequest


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
