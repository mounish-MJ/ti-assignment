from app.middleware.limiter_middleware import RateLimitMiddleware
from app.config import CustomerPolicy
from app.services.rate_limit_service import RateLimitService
from app.storage.redis_store import RedisQuotaStore
from harness.load_harness import LoadHarness, ScenarioConfig
from harness.scenarios import ScenarioFactory


def test_harness_reports_allowed_and_denied_totals():
    store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
    service = RateLimitService(store=store, quota=3)
    middleware = RateLimitMiddleware(service)
    harness = LoadHarness(middleware)

    report = harness.run_scenario(
        ScenarioConfig(customer_id="cust-harness", quota=3, request_count=5, node_ids=("node-1", "node-2"))
    )

    assert report["allowed"] == 3
    assert report["denied"] == 2
    assert report["quota"] == 3
    assert report["request_count"] == 5
    assert report["execution_model"] == "sequential"
    assert report["customer_reports"]["cust-harness"]["allowed"] == 3
    assert report["customer_reports"]["cust-harness"]["denied"] == 2
    assert report["customer_reports"]["cust-harness"]["limit"] == 3
    assert report["customer_reports"]["cust-harness"]["policy"] == "default"


def test_northwind_scenario_repeats_northwind_requests():
    store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
    service = RateLimitService(
        store=store,
        quota=3,
        window_seconds=60,
        customer_policies={"northwind": CustomerPolicy(rpm=3, policy="contracted_enterprise")},
    )
    middleware = RateLimitMiddleware(service)
    harness = LoadHarness(middleware)

    report = harness.run_scenario(ScenarioFactory.northwind_scenario())

    assert report["northwind_mode"] is True
    assert report["quota"] == 3
    assert report["request_count"] == 12
    assert report["allowed"] == 5
    assert report["denied"] == 7
    assert report["boundary_hits"] == 7
    assert report["customer_reports"]["northwind"]["allowed"] == 3
    assert report["customer_reports"]["northwind"]["denied"] == 7
    assert report["customer_reports"]["northwind"]["limit"] == 3
    assert report["customer_reports"]["northwind"]["policy"] == "contracted_enterprise"
    assert report["customer_reports"]["northwind"]["exception_applied"] is False
    assert "Execution model: sequential" in report["summary"]
    assert "Customer northwind: allowed=3 denied=7 limit=3 policy=contracted_enterprise exception_applied=False" in report["summary"]
