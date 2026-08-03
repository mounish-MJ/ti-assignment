from app.algorithms.token_bucket import TokenBucketLimiter


def test_allows_requests_until_quota_is_exhausted():
    limiter = TokenBucketLimiter(capacity=3, refill_rate=3.0)

    assert limiter.allow_request("cust-1") is True
    assert limiter.allow_request("cust-1") is True
    assert limiter.allow_request("cust-1") is True
    assert limiter.allow_request("cust-1") is False


def test_refills_over_time():
    limiter = TokenBucketLimiter(capacity=2, refill_rate=1.0)

    assert limiter.allow_request("cust-2") is True
    assert limiter.allow_request("cust-2") is True
    assert limiter.allow_request("cust-2") is False

    limiter.refill("cust-2", 1.0)

    assert limiter.allow_request("cust-2") is True
