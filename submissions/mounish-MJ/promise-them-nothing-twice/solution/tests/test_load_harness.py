from app.middleware.limiter_middleware import RateLimitMiddleware
from app.services.rate_limit_service import RateLimitService
from app.storage.redis_store import RedisQuotaStore
from harness.load_harness import LoadHarness, ScenarioConfig
from harness.scenarios import ScenarioFactory


def test_harness_supports_multiple_customers_and_nodes():
    store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
    service = RateLimitService(store=store, quota=3)
    middleware = RateLimitMiddleware(service)
    harness = LoadHarness(middleware)

    report = harness.run_scenario(
        ScenarioConfig(customer_id="cust-harness", quota=3, request_count=6, node_ids=("node-1", "node-2"))
    )

    assert report["allowed"] + report["denied"] == 6
    assert report["customers"] == ["cust-harness"]
    assert report["quota"] == 3
    assert report["customer_reports"]["cust-harness"]["allowed"] == 3
    assert report["customer_reports"]["cust-harness"]["denied"] == 3
    assert report["customer_reports"]["cust-harness"]["limit"] == 3


def test_harness_can_run_a_northwind_scenario():
    store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
    service = RateLimitService(store=store, quota=3)
    middleware = RateLimitMiddleware(service)
    harness = LoadHarness(middleware)

    report = harness.run_scenario(ScenarioFactory.northwind_scenario())

    assert report["scenario_name"] == "northwind"
    assert report["northwind_mode"] is True
    assert report["customers"] == ["northwind", "alpha", "beta"]
    assert "Allowed requests" in report["summary"]
    assert "Denied requests" in report["summary"]
    assert "northwind" in report["customer_reports"]
    assert report["customer_reports"]["northwind"]["allowed"] == 3
    assert report["customer_reports"]["northwind"]["denied"] == 7
