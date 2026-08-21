from app.core.rate_limit import check_rate_limit


def test_check_rate_limit_allows_up_to_limit_then_blocks():
    allowed_1, retry_after_1 = check_rate_limit("test-key-1", "2/minute")
    allowed_2, retry_after_2 = check_rate_limit("test-key-1", "2/minute")
    allowed_3, retry_after_3 = check_rate_limit("test-key-1", "2/minute")

    assert (allowed_1, allowed_2, allowed_3) == (True, True, False)
    assert retry_after_1 == 0
    assert retry_after_2 == 0
    assert retry_after_3 >= 0


def test_check_rate_limit_uses_independent_buckets_per_key():
    allowed_a, _ = check_rate_limit("test-key-a", "1/minute")
    allowed_b, _ = check_rate_limit("test-key-b", "1/minute")
    assert allowed_a is True
    assert allowed_b is True
