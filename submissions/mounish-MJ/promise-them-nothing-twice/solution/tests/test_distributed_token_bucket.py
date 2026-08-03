from concurrent.futures import ThreadPoolExecutor
import logging
import time
import pytest

from app.storage.redis_store import RedisQuotaStore
from app.logger import get_logger, set_request_id


def test_distributed_token_bucket_refills_and_enforces():
    # Test using fallback mode locally or redis if active
    store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True, algorithm="token_bucket")
    customer_id = "tb-test-customer"
    store.reset_customer_window(customer_id)

    # Initial capacity 2
    first_allowed, first_state = store.reserve_quota(customer_id, 1, limit=2, window_seconds=60)
    second_allowed, second_state = store.reserve_quota(customer_id, 1, limit=2, window_seconds=60)
    third_allowed, third_state = store.reserve_quota(customer_id, 1, limit=2, window_seconds=60)

    assert first_allowed is True
    assert second_allowed is True
    assert third_allowed is False
    assert third_state["retry_after"] > 0

    store.reset_customer_window(customer_id)


def test_distributed_token_bucket_refills_over_time():
    store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True, algorithm="token_bucket")
    customer_id = "tb-refill-customer"
    store.reset_customer_window(customer_id)

    # Capacity 2, window 1s (refill rate = 2/sec)
    store.reserve_quota(customer_id, 1, limit=2, window_seconds=1)
    store.reserve_quota(customer_id, 1, limit=2, window_seconds=1)
    
    # Exceeded
    denied, state = store.reserve_quota(customer_id, 1, limit=2, window_seconds=1)
    assert denied is False

    # Wait for refill
    time.sleep(1.1)

    allowed, state = store.reserve_quota(customer_id, 1, limit=2, window_seconds=1)
    assert allowed is True

    store.reset_customer_window(customer_id)


def test_request_tracing_logger_injects_ids():
    from app.logger import RequestTracingFilter
    import logging

    record = logging.LogRecord("test_tracer", logging.INFO, "pathname", 1, "Normal message", (), None)
    filtr = RequestTracingFilter()

    # Without request ID
    set_request_id(None)
    filtr.filter(record)
    assert record.request_id == ""

    # With request ID
    set_request_id("correlation-12345")
    try:
        filtr.filter(record)
        assert record.request_id == "[correlation-12345] "
    finally:
        set_request_id(None)
