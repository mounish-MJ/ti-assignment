from app.middleware.limiter_middleware import RateLimitMiddleware
from app.nodes.node_app import NodeRuntime
from app.services.rate_limit_service import RateLimitService
from app.storage.redis_store import RedisQuotaStore
from app.config import CustomerPolicy


def test_node_runtime_enforces_quota_across_nodes():
    store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
    service = RateLimitService(store=store, quota=2)
    middleware = RateLimitMiddleware(service)

    runtime_a = NodeRuntime(middleware, node_id="node-1")
    runtime_b = NodeRuntime(middleware, node_id="node-2")

    first = runtime_a.handle_request({"customer_id": "cust-1", "request_id": "req-1"})
    second = runtime_b.handle_request({"customer_id": "cust-1", "request_id": "req-2"})
    third = runtime_a.handle_request({"customer_id": "cust-1", "request_id": "req-3"})

    assert first["status"] == "accepted"
    assert second["status"] == "accepted"
    assert third["status"] == "rejected"
    assert third["reason"] == "quota_exceeded"
    assert third["limit"] == 2
    assert third["remaining"] == 0
    assert third["policy"] == "default"
    assert third["exception_applied"] is False


def test_node_runtime_includes_configured_policy_metadata():
    store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
    service = RateLimitService(
        store=store,
        quota=10,
        customer_policies={"northwind": CustomerPolicy(rpm=1, policy="contracted_enterprise")},
    )
    middleware = RateLimitMiddleware(service)
    runtime = NodeRuntime(middleware, node_id="node-1")

    first = runtime.handle_request({"customer_id": "northwind", "request_id": "northwind-1"})
    second = runtime.handle_request({"customer_id": "northwind", "request_id": "northwind-2"})

    assert first["status"] == "accepted"
    assert first["limit"] == 1
    assert first["remaining"] == 0
    assert first["policy"] == "contracted_enterprise"
    assert second["status"] == "rejected"
    assert second["limit"] == 1
    assert second["policy"] == "contracted_enterprise"


def test_node_runtime_handles_missing_customer_id():
    store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
    service = RateLimitService(store=store, quota=2)
    middleware = RateLimitMiddleware(service)
    runtime = NodeRuntime(middleware, node_id="node-3")

    response = runtime.handle_request({"request_id": "req-4"})

    assert response["status"] == "rejected"
    assert response["reason"] == "missing_customer_id"
