from app.middleware.limiter_middleware import RateLimitMiddleware
from app.models import RequestContext
from app.nodes.node_app import NodeRuntime
from app.services.rate_limit_service import RateLimitService
from app.storage.redis_store import RedisQuotaStore
from concurrent.futures import ThreadPoolExecutor
import threading


class TestBoundaryBehavior:
    def test_exactly_at_quota_is_denied_on_next_request(self):
        """A request that reaches the quota exactly should be denied on the following request."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=2)
        middleware = RateLimitMiddleware(service)

        first = middleware.evaluate(RequestContext(customer_id="boundary-1", request_id="req-1", node_id="node-a"))
        second = middleware.evaluate(RequestContext(customer_id="boundary-1", request_id="req-2", node_id="node-a"))
        third = middleware.evaluate(RequestContext(customer_id="boundary-1", request_id="req-3", node_id="node-a"))

        assert first.allowed is True
        assert second.allowed is True
        assert third.allowed is False
        assert third.reason == "quota_exceeded"

    def test_one_request_below_quota_is_allowed(self):
        """A single request below the limit should be accepted."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=3)
        middleware = RateLimitMiddleware(service)

        decision = middleware.evaluate(RequestContext(customer_id="boundary-2", request_id="req-4", node_id="node-b"))

        assert decision.allowed is True
        assert decision.reason == "allowed"

    def test_one_request_above_quota_is_denied(self):
        """A request beyond the configured quota should be rejected immediately."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=1)
        middleware = RateLimitMiddleware(service)

        first = middleware.evaluate(RequestContext(customer_id="boundary-3", request_id="req-5", node_id="node-c"))
        second = middleware.evaluate(RequestContext(customer_id="boundary-3", request_id="req-6", node_id="node-c"))

        assert first.allowed is True
        assert second.allowed is False
        assert second.reason == "quota_exceeded"

    def test_window_reset_allows_new_request_window(self):
        """Resetting a customer window should allow a fresh request window after the previous one is cleared."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=1)
        middleware = RateLimitMiddleware(service)

        first = middleware.evaluate(RequestContext(customer_id="boundary-4", request_id="req-7", node_id="node-d"))
        store.reset_customer_window("boundary-4")
        second = middleware.evaluate(RequestContext(customer_id="boundary-4", request_id="req-8", node_id="node-d"))

        assert first.allowed is True
        assert second.allowed is True
        assert second.reason == "allowed"

    def test_window_seconds_expire_customer_quota(self):
        """A customer's quota should reset after the configured window duration."""
        import time

        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=1, window_seconds=1)
        middleware = RateLimitMiddleware(service)

        first = middleware.evaluate(RequestContext(customer_id="boundary-7", request_id="req-9", node_id="node-d"))
        assert first.allowed is True

        time.sleep(1.1)

        second = middleware.evaluate(RequestContext(customer_id="boundary-7", request_id="req-10", node_id="node-d"))
        assert second.allowed is True
        assert second.reason == "allowed"

    def test_simultaneous_requests_do_not_exceed_quota(self):
        """Simultaneous requests should not allow more than the configured quota in a shared-state flow."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=2)
        middleware = RateLimitMiddleware(service)
        start = threading.Barrier(5)

        def evaluate(index: int):
            start.wait()
            return middleware.evaluate(RequestContext(customer_id="boundary-5", request_id=f"req-{index}", node_id=f"node-{index % 3}"))

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(evaluate, range(5)))

        allowed_count = sum(1 for decision in results if decision.allowed)
        denied_count = sum(1 for decision in results if not decision.allowed)

        assert allowed_count == 2
        assert denied_count == 3

    def test_multiple_customers_have_isolated_boundaries(self):
        """Different customers should have independent quota boundaries."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=1)
        middleware = RateLimitMiddleware(service)

        first_customer = middleware.evaluate(RequestContext(customer_id="customer-a", request_id="req-9", node_id="node-f"))
        second_customer = middleware.evaluate(RequestContext(customer_id="customer-b", request_id="req-10", node_id="node-f"))

        assert first_customer.allowed is True
        assert second_customer.allowed is True

    def test_multi_node_behavior_respects_shared_quota(self):
        """Requests routed through multiple nodes should still be limited by the same shared quota."""
        store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
        service = RateLimitService(store=store, quota=1)
        middleware = RateLimitMiddleware(service)

        runtime_a = NodeRuntime(middleware, node_id="node-1")
        runtime_b = NodeRuntime(middleware, node_id="node-2")

        first = runtime_a.handle_request({"customer_id": "boundary-6", "request_id": "req-11"})
        second = runtime_b.handle_request({"customer_id": "boundary-6", "request_id": "req-12"})

        assert first["status"] == "accepted"
        assert second["status"] == "rejected"
        assert second["reason"] == "quota_exceeded"
