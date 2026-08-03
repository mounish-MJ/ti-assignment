# RelayAPI Distributed Rate Limiter

## Project Overview

This repository implements a prototype distributed rate limiter for RelayAPI. The system is designed to enforce per-customer request quotas across multiple application nodes while keeping the enforcement logic testable and explainable.

The current implementation is intentionally modular and milestone-oriented. It covers:
- a local token-bucket reference algorithm,
- a shared-state storage abstraction,
- a middleware-style request decision layer,
- a node-level request runtime,
- and a lightweight sequential harness for synthetic traffic.

This is a strong engineering prototype, but it is not yet a production-grade distributed control plane.

## Architecture

The project is organized around a small layered architecture:

1. Request entry
   - The node runtime accepts payload-like request data and converts it into a normalized request context.

2. Policy evaluation
   - The middleware and rate-limit service evaluate whether the request should be allowed or rejected.

3. Shared state
   - The storage abstraction provides access to customer usage state. The current implementation uses a Redis-backed store when available and falls back to an in-process model when Redis is not reachable.

4. Simulation and testing
   - The harness drives the same request path with sequential synthetic traffic to demonstrate boundary behavior and quota enforcement.

### Key modules
- app/config.py: YAML-based configuration loading
- app/models.py: request and decision data models
- app/algorithms/token_bucket.py: local token-bucket limiter reference
- app/storage/: shared-state abstraction and Redis-backed implementation
- app/services/: rate-limit evaluation service
- app/middleware/: middleware wrapper around the service
- app/nodes/: node-level request runtime
- harness/: synthetic load-generation utilities and scenario definitions
- tests/: unit, integration, and boundary test suites

## Technology Stack

- Python 3.10+
- PyYAML for configuration parsing
- pytest for automated testing
- Redis-compatible storage backend for shared-state coordination (when available)

## Setup Instructions

### Prerequisites
- Python 3.10 or newer
- pip
- Optional: a Redis server for shared-state testing

### Install dependencies

```bash
pip install -r requirements.txt
```

### Project layout

```text
app/
  algorithms/
  middleware/
  nodes/
  services/
  storage/
config/
  default.yaml
harness/
tests/
```

## Running the Service

The project now exposes a FastAPI application with a production-ready HTTP entry point.

### Start the API server

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Available endpoints

- `GET /health` — health check
- `POST /request` — rate limiter entry point

### POST /request

Headers:
- `X-Customer-Id`: customer identifier

Body:

```json
{
  "request_id": "req-1"
}
```

Success response:

```json
{
  "status": "accepted",
  "reason": "allowed",
  "customer_id": "cust-1",
  "request_id": "req-1",
  "node_id": "node-1"
}
```

Rate limit exceeded response:

- status code: `429`
- header: `Retry-After`

```json
{
  "status": "rejected",
  "reason": "quota_exceeded",
  "customer_id": "cust-1",
  "request_id": "req-2",
  "node_id": "node-1",
  "retry_after": 58
}
```

Example:

```python
from app.middleware.limiter_middleware import RateLimitMiddleware
from app.nodes.node_app import NodeRuntime
from app.services.rate_limit_service import RateLimitService
from app.storage.redis_store import RedisQuotaStore

store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
service = RateLimitService(store=store, quota=2)
middleware = RateLimitMiddleware(service)
runtime = NodeRuntime(middleware, node_id="node-1")

response = runtime.handle_request({"customer_id": "cust-1", "request_id": "req-1"})
print(response)
```

## Running the Scenario Harness

The harness simulates sequential traffic across multiple customers and node runtimes. It is useful for boundary demonstrations, but it is not a proof of distributed race safety.

Example:

```python
from app.middleware.limiter_middleware import RateLimitMiddleware
from app.services.rate_limit_service import RateLimitService
from app.storage.redis_store import RedisQuotaStore
from harness.load_harness import LoadHarness
from harness.scenarios import ScenarioFactory

store = RedisQuotaStore(host="localhost", port=6379, db=0, decode_responses=True)
service = RateLimitService(store=store, quota=3)
middleware = RateLimitMiddleware(service)
harness = LoadHarness(middleware)

report = harness.run_scenario(ScenarioFactory.northwind_scenario())
print(report["summary"])
print(report)
```

Run the harness from the project root:

```bash
python -m harness --scenario northwind --quota 3 --requests 12
```

For a custom run:

```bash
python -m harness --scenario custom --customer-id cust-harness --requests 10 --quota 3 --node-ids node-1,node-2
```

## Running Tests

Run the full test suite:

```bash
python -m pytest -q
```

Run the complete suite with verbose output:

```bash
python -m pytest -q tests
```

## Verification Commands

From the repository root:

```bash
python -m pip install -r requirements.txt
```

Start Redis if you want distributed shared-state behavior:

```bash
redis-server
```

If Redis is not available, the implementation falls back to an in-process store for local development.

Start the FastAPI app:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Run the test suite:

```bash
python -m pytest -q
```

Run the load harness:

```bash
python -m harness --scenario northwind --quota 3 --requests 12
```

Or use a custom harness run:

```bash
python -m harness --scenario custom --customer-id cust-harness --requests 10 --quota 3 --node-ids node-1,node-2
```

## Design Decisions

### 1. Layered request flow
The design separates request intake, policy evaluation, and shared-state access so the system can evolve without entangling the core decision logic with transport concerns.

### 2. Shared-state abstraction
The storage interface decouples the limiter service from the store implementation. This is important for future swap-in of Redis, an in-memory adapter, or a stronger coordination backend.

### 3. Token bucket as a reference model
The token-bucket implementation is included as a local reference algorithm. It is useful for understanding rate-limiting semantics, even though the actual distributed enforcement path currently uses a simpler shared counter model.

### 4. Middleware-oriented request handling
The middleware and node runtime are intentionally lightweight so the limiter can later be integrated into an HTTP framework or API gateway without rewriting the core policy logic.

## Assumptions

- Each incoming request can be associated with a customer ID.
- The system is being evaluated as a prototype and not yet a complete production deployment.
- Redis is available for distributed behavior when configured; otherwise the implementation falls back to an in-process model for local development.
- Quotas are enforced as simple request counts per customer within a configured window.

## Limitations

- The Redis shared-state path uses optimistic Redis transactions for reservation. A Lua script would be a stronger production hardening step.
- The current service uses a simple quota counter rather than a more sophisticated time-window or token-bucket enforcement model in the distributed path.
- The harness is synthetic, sequential, and intended for demonstration rather than high-performance benchmarking or concurrency proof.
- The implementation does not yet provide a full observability layer, security hardening, or production failure policy.

## Future Improvements

- Move the Redis reservation flow to a Lua script.
- Introduce a production-grade failure policy for Redis outages and dependency latency.
- Add structured logging, metrics, and traces for accepted and denied requests.
- Expand the HTTP API from a prototype entry point into a production-ready service surface.
- Add richer scenario generation for burst traffic, retries, and hot-customer patterns.
- Integrate configuration more deeply into quota policy and node behavior.
- Harden secret handling and remove any environment-specific hardcoded values from non-demo code.

## Reviewer Notes

This project is best understood as a milestone-based prototype that demonstrates the architecture and request flow for a distributed rate limiter. It is appropriate for review of structure, layering, and testing discipline, but it should not yet be treated as a production-ready rate-limiting platform.
