from pathlib import Path

import pytest

from app.config import load_config
from app.middleware.limiter_middleware import RateLimitMiddleware
from app.models import RequestContext
from app.nodes.node_app import NodeRuntime
from app.services.rate_limit_service import RateLimitService
from app.storage.redis_store import RedisQuotaStore


class TestIntegrationRequestFlow:
    def test_request_flow_allows_and_denies_across_nodes(self):
        """A full request path should allow the first requests and deny later ones across different node runtimes."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=2)
        middleware = RateLimitMiddleware(service)

        runtime_a = NodeRuntime(middleware, node_id="node-1")
        runtime_b = NodeRuntime(middleware, node_id="node-2")

        first = runtime_a.handle_request({"customer_id": "cust-a", "request_id": "flow-1"})
        second = runtime_b.handle_request({"customer_id": "cust-a", "request_id": "flow-2"})
        third = runtime_a.handle_request({"customer_id": "cust-a", "request_id": "flow-3"})

        assert first["status"] == "accepted"
        assert second["status"] == "accepted"
        assert third["status"] == "rejected"
        assert third["reason"] == "quota_exceeded"

    def test_request_flow_isolated_per_customer(self):
        """Each customer should have an independent quota count rather than sharing a global counter."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=1)
        middleware = RateLimitMiddleware(service)
        runtime = NodeRuntime(middleware, node_id="node-3")

        first_customer = runtime.handle_request({"customer_id": "cust-1", "request_id": "req-1"})
        second_customer = runtime.handle_request({"customer_id": "cust-2", "request_id": "req-2"})

        assert first_customer["status"] == "accepted"
        assert second_customer["status"] == "accepted"

    def test_request_flow_rejects_missing_customer_id(self):
        """A request without a customer ID should be rejected through the full request path."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=2)
        middleware = RateLimitMiddleware(service)
        runtime = NodeRuntime(middleware, node_id="node-4")

        response = runtime.handle_request({"request_id": "req-4"})

        assert response["status"] == "rejected"
        assert response["reason"] == "missing_customer_id"


class TestIntegrationConfiguration:
    def test_configuration_is_used_for_runtime_defaults(self):
        """Configuration should load with the expected default values for the runtime environment."""
        config_path = Path("config/default.yaml")
        config = load_config(config_path)

        assert config.default_rpm == 100
        assert config.window_seconds == 60
        assert config.strict_mode is True


class TestIntegrationStoreBehavior:
    def test_store_reset_prepares_next_window(self):
        """Resetting a customer window should clear the stored usage so the next window starts cleanly."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)

        store.increment_customer_usage("window-customer", 2)
        state_before_reset = store.get_customer_state("window-customer")
        store.reset_customer_window("window-customer")
        state_after_reset = store.get_customer_state("window-customer")

        assert state_before_reset["usage"] == 2
        assert state_after_reset == {}

    def test_store_handles_multiple_customers_independently(self):
        """Different customers should be tracked independently in the shared store."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)

        store.increment_customer_usage("customer-a", 1)
        store.increment_customer_usage("customer-b", 2)

        first_state = store.get_customer_state("customer-a")
        second_state = store.get_customer_state("customer-b")

        assert first_state["usage"] == 1
        assert second_state["usage"] == 2


class TestIntegrationMiddlewareDecisioning:
    def test_middleware_returns_consistent_decision_for_same_context(self):
        """The middleware should return a stable decision result for the same request context."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=1)
        middleware = RateLimitMiddleware(service)

        request_context = RequestContext(customer_id="cust-consistent", request_id="req-10", node_id="node-5")
        first_decision = middleware.evaluate(request_context)
        second_decision = middleware.evaluate(request_context)

        assert first_decision.allowed is True
        assert second_decision.allowed is False
        assert second_decision.reason == "quota_exceeded"
