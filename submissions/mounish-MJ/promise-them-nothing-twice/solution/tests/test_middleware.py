from app.models import RequestContext
from app.middleware.limiter_middleware import RateLimitMiddleware
from app.services.rate_limit_service import RateLimitService
from app.storage.redis_store import RedisQuotaStore


def test_middleware_allows_requests_until_quota_is_exhausted():
    store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
    service = RateLimitService(store=store, quota=2)
    middleware = RateLimitMiddleware(service)

    first = middleware.evaluate(RequestContext(customer_id="cust-1", request_id="req-1", node_id="node-a"))
    second = middleware.evaluate(RequestContext(customer_id="cust-1", request_id="req-2", node_id="node-a"))
    third = middleware.evaluate(RequestContext(customer_id="cust-1", request_id="req-3", node_id="node-a"))

    assert first.allowed is True
    assert second.allowed is True
    assert third.allowed is False
    assert third.reason == "quota_exceeded"


def test_middleware_rejects_missing_customer_id():
    store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
    service = RateLimitService(store=store, quota=2)
    middleware = RateLimitMiddleware(service)

    decision = middleware.evaluate(RequestContext(customer_id="", request_id="req-4", node_id="node-b"))

    assert decision.allowed is False
    assert decision.reason == "missing_customer_id"
