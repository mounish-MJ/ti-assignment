from pathlib import Path

import pytest

from app.config import Config, CustomerPolicy, load_config
from app.logger import get_logger
from app.middleware.limiter_middleware import RateLimitMiddleware
from app.models import RequestContext
from app.nodes.node_app import NodeRuntime
from app.services.rate_limit_service import RateLimitService
from app.storage.redis_store import RedisQuotaStore


class DummyStore:
    def __init__(self, initial_usage: int = 0):
        self.initial_usage = initial_usage
        self.calls = []

    def get_customer_state(self, customer_id: str):
        self.calls.append(("get", customer_id))
        return {"customer_id": customer_id, "usage": self.initial_usage}

    def increment_customer_usage(self, customer_id: str, quota: int, window_seconds: int | None = None):
        self.calls.append(("increment", customer_id, quota, window_seconds))
        self.initial_usage += quota
        return {"customer_id": customer_id, "usage": self.initial_usage}

    def reset_customer_window(self, customer_id: str):
        self.calls.append(("reset", customer_id))
        self.initial_usage = 0


class ReservationStore:
    def __init__(self, initial_usage: int = 0):
        self.initial_usage = initial_usage
        self.calls = []

    def get_customer_state(self, customer_id: str):
        self.calls.append(("get", customer_id))
        return {"customer_id": customer_id, "usage": 0}

    def increment_customer_usage(self, customer_id: str, quota: int, window_seconds: int | None = None):
        self.calls.append(("increment", customer_id, quota, window_seconds))
        self.initial_usage += quota
        return {"customer_id": customer_id, "usage": self.initial_usage}

    def reserve_quota(self, customer_id: str, quota: int, limit: int, window_seconds: int | None = None):
        self.calls.append(("reserve", customer_id, quota, limit, window_seconds))
        if self.initial_usage + quota > limit:
            return False, {"customer_id": customer_id, "usage": self.initial_usage}
        self.initial_usage += quota
        return True, {"customer_id": customer_id, "usage": self.initial_usage}

    def reset_customer_window(self, customer_id: str):
        self.calls.append(("reset", customer_id))
        self.initial_usage = 0


class TestConfigLoading:
    def test_load_config_from_default_file(self):
        config_path = Path("config/default.yaml")
        config = load_config(config_path)

        assert isinstance(config, Config)
        assert config.default_rpm == 100
        assert config.window_seconds == 60
        assert config.strict_mode is True
        assert config.customer_overrides == {}
        assert config.customers["northwind"] == CustomerPolicy(rpm=300, policy="contracted_enterprise")

    def test_load_config_uses_default_values_for_missing_keys(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_rpm: 250\n", encoding="utf-8")

        config = load_config(config_file)

        assert config.default_rpm == 250
        assert config.window_seconds == 60
        assert config.strict_mode is True
        assert config.customer_overrides == {}
        assert config.customers == {}

    def test_load_config_rejects_non_numeric_values(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("default_rpm: not-a-number\n", encoding="utf-8")

        with pytest.raises(ValueError):
            load_config(config_file)


class TestLogger:
    def test_logger_initializes_with_name(self):
        logger = get_logger("unit-tests")

        assert logger.name == "unit-tests"


class TestRateLimitService:
    def test_allows_requests_below_quota(self):
        store = DummyStore(initial_usage=0)
        service = RateLimitService(store=store, quota=2)

        decision = service.evaluate_request(RequestContext(customer_id="cust-1", request_id="req-1", node_id="node-a"))

        assert decision.allowed is True
        assert decision.reason == "allowed"
        assert store.initial_usage == 1

    def test_denies_requests_when_quota_is_exhausted(self):
        store = DummyStore(initial_usage=2)
        service = RateLimitService(store=store, quota=2)

        decision = service.evaluate_request(RequestContext(customer_id="cust-1", request_id="req-2", node_id="node-a"))

        assert decision.allowed is False
        assert decision.reason == "quota_exceeded"
        assert store.initial_usage == 2

    def test_rejects_empty_customer_id(self):
        store = DummyStore(initial_usage=0)
        service = RateLimitService(store=store, quota=2)

        decision = service.evaluate_request(RequestContext(customer_id="", request_id="req-3", node_id="node-a"))

        assert decision.allowed is False
        assert decision.reason == "missing_customer_id"
        assert store.initial_usage == 0

    def test_uses_reservation_path_for_admission_control(self):
        store = ReservationStore(initial_usage=0)
        service = RateLimitService(store=store, quota=1)

        first = service.evaluate_request(RequestContext(customer_id="cust-reserve", request_id="req-res-1", node_id="node-a"))
        second = service.evaluate_request(RequestContext(customer_id="cust-reserve", request_id="req-res-2", node_id="node-a"))

        assert first.allowed is True
        assert second.allowed is False
        assert any(call[0] == "reserve" for call in store.calls)

    def test_uses_store_retry_after_metadata_for_denials(self):
        class RetryAfterStore(ReservationStore):
            def reserve_quota(self, customer_id: str, quota: int, limit: int, window_seconds: int | None = None):
                self.calls.append(("reserve", customer_id, quota, limit, window_seconds))
                return False, {"customer_id": customer_id, "usage": limit, "retry_after": 7}

        store = RetryAfterStore(initial_usage=0)
        service = RateLimitService(store=store, quota=1, window_seconds=60)

        decision = service.evaluate_request(RequestContext(customer_id="cust-retry", request_id="req-retry", node_id="node-a"))

        assert decision.allowed is False
        assert decision.reason == "quota_exceeded"
        assert decision.retry_after == 7

    def test_uses_configured_customer_policy_limit(self):
        store = ReservationStore(initial_usage=0)
        service = RateLimitService(
            store=store,
            quota=10,
            customer_policies={"cust-small": CustomerPolicy(rpm=1, policy="contracted_small")},
        )

        first = service.evaluate_request(RequestContext(customer_id="cust-small", request_id="req-policy-1", node_id="node-a"))
        second = service.evaluate_request(RequestContext(customer_id="cust-small", request_id="req-policy-2", node_id="node-a"))

        assert first.allowed is True
        assert first.limit == 1
        assert first.remaining == 0
        assert first.policy == "contracted_small"
        assert second.allowed is False
        assert second.limit == 1
        assert second.policy == "contracted_small"
        assert ("reserve", "cust-small", 1, 1, 60) in store.calls

    def test_unknown_customer_uses_default_policy(self):
        store = ReservationStore(initial_usage=0)
        service = RateLimitService(store=store, quota=2)

        decision = service.evaluate_request(RequestContext(customer_id="unknown", request_id="req-default", node_id="node-a"))

        assert decision.allowed is True
        assert decision.limit == 2
        assert decision.remaining == 1
        assert decision.policy == "default"
        assert decision.exception_applied is False

    def test_configured_exception_is_metadata_not_hidden_bypass(self):
        store = ReservationStore(initial_usage=0)
        service = RateLimitService(
            store=store,
            quota=1,
            customer_policies={
                "northwind": CustomerPolicy(
                    rpm=2,
                    policy="approved_batch_exception",
                    exception=True,
                    audit_reason="renewal-approved temporary batch relief",
                )
            },
        )

        first = service.evaluate_request(RequestContext(customer_id="northwind", request_id="northwind-1", node_id="node-a"))
        second = service.evaluate_request(RequestContext(customer_id="northwind", request_id="northwind-2", node_id="node-a"))
        third = service.evaluate_request(RequestContext(customer_id="northwind", request_id="northwind-3", node_id="node-a"))

        assert first.allowed is True
        assert second.allowed is True
        assert third.allowed is False
        assert third.limit == 2
        assert third.policy == "approved_batch_exception"
        assert third.exception_applied is True
        assert ("reserve", "northwind", 1, 2, 60) in store.calls


class TestMiddleware:
    def test_middleware_returns_decision_result(self):
        store = DummyStore(initial_usage=0)
        service = RateLimitService(store=store, quota=1)
        middleware = RateLimitMiddleware(service)

        decision = middleware.evaluate(RequestContext(customer_id="cust-2", request_id="req-4", node_id="node-b"))

        assert decision.allowed is True
        assert decision.reason == "allowed"


class TestNodeRuntime:
    def test_node_runtime_returns_structured_response_for_allowed_request(self):
        store = DummyStore(initial_usage=0)
        service = RateLimitService(store=store, quota=1)
        middleware = RateLimitMiddleware(service)
        runtime = NodeRuntime(middleware, node_id="node-c")

        response = runtime.handle_request({"customer_id": "cust-3", "request_id": "req-5"})

        assert response["status"] == "accepted"
        assert response["reason"] == "allowed"

    def test_node_runtime_returns_structured_response_for_rejected_request(self):
        store = DummyStore(initial_usage=1)
        service = RateLimitService(store=store, quota=1)
        middleware = RateLimitMiddleware(service)
        runtime = NodeRuntime(middleware, node_id="node-d")

        response = runtime.handle_request({"customer_id": "cust-4", "request_id": "req-6"})

        assert response["status"] == "rejected"
        assert response["reason"] == "quota_exceeded"

    def test_node_runtime_handles_missing_customer_id(self):
        store = DummyStore(initial_usage=0)
        service = RateLimitService(store=store, quota=1)
        middleware = RateLimitMiddleware(service)
        runtime = NodeRuntime(middleware, node_id="node-e")

        response = runtime.handle_request({"request_id": "req-7"})

        assert response["status"] == "rejected"
        assert response["reason"] == "missing_customer_id"


class TestRedisStore:
    def test_store_implements_interface(self):
        assert issubclass(RedisQuotaStore, object)

    def test_store_returns_empty_state_for_missing_customer(self):
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)

        assert store.get_customer_state("missing-customer") == {}

    def test_store_resets_customer_state(self):
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)

        store.increment_customer_usage("cust-reset", 1)
        store.reset_customer_window("cust-reset")

        assert store.get_customer_state("cust-reset") == {}
