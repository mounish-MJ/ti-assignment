import pytest
from concurrent.futures import ThreadPoolExecutor

from app.storage.interfaces import QuotaStoreInterface
from app.storage.redis_store import RedisQuotaStore


@pytest.fixture
def store():
    return RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)


def test_store_implements_interface():
    assert issubclass(RedisQuotaStore, QuotaStoreInterface)


def test_store_handles_missing_customer_state(store):
    state = store.get_customer_state("missing-customer")

    assert state == {}


def test_store_exposes_backend_mode(store):
    assert store.backend_mode in {"redis", "fallback"}


def test_increment_and_reset_customer_usage(store):
    customer_id = "cust-1"

    store.increment_customer_usage(customer_id, 3)
    state_after_increment = store.get_customer_state(customer_id)

    assert state_after_increment["customer_id"] == customer_id
    assert state_after_increment["usage"] == 3

    store.reset_customer_window(customer_id)
    state_after_reset = store.get_customer_state(customer_id)

    assert state_after_reset == {}


def test_reserve_quota_denial_does_not_increment_usage(store):
    customer_id = "reserve-denial-customer"
    store.reset_customer_window(customer_id)

    first_allowed, first_state = store.reserve_quota(customer_id, 1, limit=1, window_seconds=60)
    second_allowed, second_state = store.reserve_quota(customer_id, 1, limit=1, window_seconds=60)
    final_state = store.get_customer_state(customer_id)

    assert first_allowed is True
    assert first_state["usage"] == 1
    assert second_allowed is False
    assert second_state["usage"] == 1
    assert final_state["usage"] == 1

    store.reset_customer_window(customer_id)


def test_reserve_quota_returns_retry_after_when_window_is_known(store):
    customer_id = "reserve-retry-after-customer"
    store.reset_customer_window(customer_id)

    store.reserve_quota(customer_id, 1, limit=1, window_seconds=60)
    allowed, state = store.reserve_quota(customer_id, 1, limit=1, window_seconds=60)

    assert allowed is False
    assert state["retry_after"] > 0
    assert state["retry_after"] <= 60

    store.reset_customer_window(customer_id)


def test_real_redis_reservation_is_atomic_when_redis_is_available():
    store = RedisQuotaStore(host="localhost", port=6379, db=15, decode_responses=True)
    if store.backend_mode != "redis":
        pytest.skip("Redis is not available; fallback mode is not a distributed Redis coordination test")

    customer_id = "redis-atomic-customer"
    store.reset_customer_window(customer_id)

    def reserve(index: int):
        return store.reserve_quota(customer_id, 1, limit=3, window_seconds=60)[0]

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(reserve, range(20)))

    assert sum(1 for allowed in results if allowed) == 3
    assert store.get_customer_state(customer_id)["usage"] == 3

    store.reset_customer_window(customer_id)
