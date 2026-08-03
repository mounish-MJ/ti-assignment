# Decision Record: Distributed Rate Limiter for RelayAPI

## Summary

I recommend a strict, customer-scoped rate limiter that enforces each customer's configured quota against shared state so that requests routed to any of the three stateless nodes are evaluated consistently when Redis is available. The implementation prioritizes correctness, explicit policy, and auditability over hidden customer-specific behavior.

## 1. Conflict Resolution

The main stakeholder conflict was between contractual quota enforcement and Northwind's customer experience. Priya Nair requires hard enforcement: a customer must never exceed its contracted quota, and hidden bypasses are not acceptable. Marcus Webb requires that Northwind never see a 429 during its 02:00-04:00 UTC batch window because Northwind is commercially critical.

I choose to prioritize the promise that no customer exceeds its configured effective quota. I explicitly reject a hidden Northwind bypass in application code. If the business grants Northwind temporary relief, that exception must be explicit, configurable, and auditable; the limiter should enforce configured policy, not secretly treat one customer differently.

## 2. Algorithm Choice

I selected a simple quota-counter approach for the distributed path, with a token-bucket implementation retained as a local reference model. The token bucket is useful for reasoning about burst behavior and smoothing, but Northwind's 90-120 minute batch overage is not a short burst. A shared counter is a better fit for the chosen hard-quota policy because it is easier to explain, audit, and test at the boundary.

## 3. Distributed Coordination

The system uses a shared-state abstraction with Redis as the intended coordination layer. The reason is straightforward: quota decisions must be consistent across nodes, and node-local memory cannot satisfy that requirement. Redis provides a practical path to cross-node visibility and is compatible with the assignment’s expectation of a distributed solution. The current prototype uses a fallback path when Redis is unavailable, but that fallback is a development convenience, not the production model.

## 4. Verification Strategy

Verification is designed around three layers:

- Unit tests for core logic and policy boundaries.
- Integration tests for the shared-state path and request flow through the service and runtime layers.
- A synthetic harness that exercises multiple customers, multiple node runtimes, and repeated traffic to demonstrate boundary behavior.

This strategy is intentionally pragmatic: it validates correctness under normal sequential conditions and confirms policy behavior at the quota edge. Race safety must be tested separately with concurrent tests and, for true distributed correctness, with Redis-backed coordination.

## 5. Trade-offs

The chosen design favors correctness and operational clarity over maximal sophistication. That means:

- The distributed path is simpler than a fully tuned sliding-window or burst-aware algorithm.
- The implementation is easier to reason about, debug, and present to reviewers.
- The design is intentionally conservative and may be less feature-rich than a production-grade throttling engine.

The trade-off is acceptable for the current problem because the assignment is fundamentally about demonstrating correctness and policy discipline under distributed conditions.

## 6. What the Harness Proves

The harness proves that the limiter follows the expected policy for sequential synthetic traffic routed across multiple node runtimes. It demonstrates boundary behavior and customer isolation, including the Northwind repeated-overage scenario.

## 7. What It Does Not Prove

The harness does not prove production readiness or distributed race safety. It does not validate long-duration stability, real Redis failover behavior, latency under production traffic, or full observability and operational resilience.

## 8. What I Would Build with Another Four Hours

With another four hours, I would harden the coordinator rather than expand the feature set. I would move the Redis reservation into a Lua script, add explicit production failure handling for Redis unavailability, and improve decision metadata. I would also add structured logging and counters so that support and operations can inspect allowed versus denied decisions with confidence.
