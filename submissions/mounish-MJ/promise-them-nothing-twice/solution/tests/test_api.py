import importlib

from fastapi.testclient import TestClient

import app.main as app_main


def test_health_endpoint():
    client = TestClient(app_main.app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_endpoint_rejects_missing_customer_header():
    client = TestClient(app_main.app)
    response = client.post("/request", json={"request_id": "req-1"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing X-Customer-Id header"


def test_request_endpoint_allows_and_denies_requests(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_QUOTA", "2")
    reloaded = importlib.reload(app_main)
    client = TestClient(reloaded.app)
    headers = {"X-Customer-Id": "cust-api-1"}

    response1 = client.post("/request", json={"request_id": "req-1"}, headers=headers)
    response2 = client.post("/request", json={"request_id": "req-2"}, headers=headers)
    response3 = client.post("/request", json={"request_id": "req-3"}, headers=headers)

    assert response1.status_code == 200
    assert response1.json()["status"] == "accepted"

    assert response2.status_code == 200
    assert response2.json()["status"] == "accepted"

    assert response3.status_code == 429
    assert response3.json()["status"] == "rejected"
    assert response3.headers["Retry-After"] == "60"
    assert response3.json()["limit"] == 2
    assert response3.json()["policy"] == "default"


def test_request_endpoint_uses_runtime_retry_after(monkeypatch):
    class RejectingRuntime:
        def handle_request(self, payload):
            return {
                "status": "rejected",
                "reason": "quota_exceeded",
                "customer_id": payload["customer_id"],
                "request_id": payload["request_id"],
                "node_id": "node-test",
                "retry_after": 7,
            }

    monkeypatch.setattr(app_main, "runtime", RejectingRuntime())
    client = TestClient(app_main.app)

    response = client.post("/request", json={"request_id": "req-retry"}, headers={"X-Customer-Id": "cust-api-retry"})

    assert response.status_code == 429
    assert response.json()["retry_after"] == 7
    assert response.headers["Retry-After"] == "7"


def test_request_endpoint_uses_configured_customer_policy(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_QUOTA", "1")
    reloaded = importlib.reload(app_main)
    client = TestClient(reloaded.app)
    headers = {"X-Customer-Id": "acme"}

    response1 = client.post("/request", json={"request_id": "acme-1"}, headers=headers)
    response2 = client.post("/request", json={"request_id": "acme-2"}, headers=headers)

    assert response1.status_code == 200
    assert response1.json()["limit"] == 100
    assert response1.json()["policy"] == "contracted_standard"
    assert response1.json()["remaining"] == 99

    assert response2.status_code == 200
    assert response2.json()["limit"] == 100
    assert response2.json()["policy"] == "contracted_standard"
    assert response2.json()["remaining"] == 98
