# Software Requirements Specification (SRS)

## Project: Distributed Rate Limiter for RelayAPI

> This SRS is based on the assignment context provided in the prompt and the earlier project brief. No implementation code has been written.

---

## 1. Purpose

RelayAPI requires a distributed rate limiter that enforces customer-based request quotas across multiple application nodes. The system must remain correct even when traffic is distributed randomly across three stateless application instances and when many requests arrive concurrently.

The solution must balance correctness, operational simplicity, customer experience, and policy clarity.

---

## 1A. Design Review Findings and Improvements

### A. Missing requirements identified

The original analysis captured the core problem, but several requirements should be made explicit to avoid downstream ambiguity.

| Area | Missing requirement | Why it matters |
|---|---|---|
| Request identity | The system must clearly identify the customer from each request in a stable and unambiguous way. | Without a reliable identity source, enforcement is impossible. |
| Policy semantics | The system must define whether a request is rejected, throttled, delayed, or partially accepted when the quota is exceeded. | This directly affects customer experience and support expectations. |
| Dependency failure behavior | The system must define behavior when the shared state store is unavailable or slow. | Production systems must fail in a predictable and safe way. |
| Response contract | The system must define the API response shape, status code, and headers for denied requests. | This is necessary for client behavior and observability. |
| Operational visibility | The system must expose counters, decision logs, and metrics for each customer and rate-limiter outcome. | Engineers and support need accountability and diagnostics. |
| Admin controls | The system should support configuration changes without code changes. | Quotas and policy changes are operational concerns. |
| Data hygiene | The system must define how old quota windows are expired or cleaned up. | Prevents stale state and incorrect long-term growth. |

### B. Incorrect assumptions that should be challenged

The first version made several assumptions that should be treated as design decisions, not facts.

| Assumption | Why it is risky | Better framing |
|---|---|---|
| A shared store is always available | This is not guaranteed in production and changes the failure model significantly. | The system should define a degraded-mode policy. |
| A hard deny is the right default | That may be too strict for customer experience or support operations. | The policy should be explicitly chosen and documented. |
| Quotas are strictly per minute with no burst tolerance | Real systems often need a small burst allowance or a smoothing policy. | Burst behavior must be explicitly specified. |
| The customer identity is always available and trustworthy | In practice, identity may be inferred or inconsistent across services. | The design should define the identity source and validation approach. |
| The implementation will be judged primarily on algorithmic elegance | The assignment also tests operational clarity and policy reasoning. | The solution should optimize for correctness and explainability. |

### C. Hidden risks that should be elevated

| Risk | Why it is serious |
|---|---|
| Clock skew or clock drift | Time-based windows can become inconsistent across services and shared stores. |
| Duplicate or retried requests | The same logical request may be processed more than once, causing quota distortion. |
| Partial failure in the coordination layer | A single dependency failure may create a false sense of safety or a false deny. |
| Support escalation from customer-facing false positives | Strict enforcement without clear communication can hurt customer trust. |
| Operational misunderstanding | Engineers may implement the letter of the policy but fail the business intent. |

### D. Stakeholder questions that should be answered before implementation

| Stakeholder | Question |
|---|---|
| CTO | Should the platform enforce a strict hard cap, or is a throttling policy acceptable under exceptional conditions? |
| Support Lead | What is the acceptable customer experience when a customer exceeds its quota? |
| Product | Is a burst allowance acceptable, or is the quota expected to be absolute? |
| Operations | What should happen when the shared state service becomes unavailable? |
| Engineering | How much latency overhead is acceptable for each admission decision? |

### E. Possible misunderstandings to avoid

| Possible misunderstanding | Clarification |
|---|---|
| “RPM” means requests per minute in a rolling sense | The assignment should define whether the window is fixed or rolling. |
| Rate limiting is only a traffic-control problem | It is also a policy, customer-experience, and operations problem. |
| A distributed solution can rely on local node state | That would violate the core requirement of cross-node correctness. |
| The Northwind case is only a data issue | It is also a policy and stakeholder-alignment issue. |
| The final system only needs to be correct in a test environment | It must also be explainable and operable under real production constraints. |

### F. Revised requirement emphasis

The analysis should be refined to place equal weight on the following:

1. Correctness under concurrency.
2. Policy clarity and stakeholder alignment.
3. Safe failure behavior.
4. Clear operational visibility.
5. A realistic and testable contract for allowed and denied requests.

---

## 2. Product Summary

The system will decide, for each incoming request, whether that request is allowed or denied based on the customer’s configured requests-per-minute (RPM) quota. The decision must be made using shared state so that quota accounting is consistent across all nodes.

The assignment also requires a load-testing harness, boundary-behavior demonstrations, and a written decision record explaining the policy chosen for contentious cases such as Northwind’s repeated nightly overage.

---

## 3. Business Requirements

| ID | Requirement | Rationale | Priority |
|---|---|---|---|
| BR-1 | Enforce per-customer RPM quotas consistently. | Prevents abuse and ensures quota commitments are honored. | High |
| BR-2 | Protect API availability and service quality under load. | Rate limiting preserves platform stability. | High |
| BR-3 | Prevent customers from bypassing quotas through distributed request distribution. | Random load balancing must not weaken enforcement. | High |
| BR-4 | Provide a clear policy for customers who exceed their quota repeatedly. | The Northwind scenario requires a defensible operational decision. | High |
| BR-5 | Deliver a demonstrable and testable solution. | The assignment requires evidence of correctness and boundary behavior. | High |
| BR-6 | Produce documentation that explains policy choices and tradeoffs. | Stakeholders need transparency and auditability. | Medium |

---

## 4. Functional Requirements

| ID | Requirement | Description |
|---|---|---|
| FR-1 | Customer-based decisioning | The system must evaluate each request against the requesting customer’s quota. |
| FR-2 | Distributed enforcement | The limiter must work correctly when requests are served by any of three stateless application nodes. |
| FR-3 | Shared quota state | Quota counts must be stored and updated in shared state accessible by all nodes. |
| FR-4 | Atomic admission | A request must be either fully admitted or fully rejected for a given quota window; no partial or duplicate admission is allowed. |
| FR-5 | Quota windowing | The system must support quota evaluation over a defined time window, such as per minute. |
| FR-6 | Over-limit handling | Requests that exceed the quota must be rejected or otherwise handled according to the chosen policy. |
| FR-7 | Boundary behavior | The system must clearly distinguish between allowed, exactly-at-limit, and over-limit requests. |
| FR-8 | Per-customer observability | The system should make it possible to observe whether a request was allowed or denied and why. |
| FR-9 | Load harness | The solution must include a harness that can generate traffic and demonstrate behavior under load. |
| FR-10 | Decision documentation | The project must include a written explanation of policy decisions, especially for contentious cases. |

---

## 5. Technical Requirements

| ID | Requirement | Notes |
|---|---|---|
| TR-1 | Distributed architecture | The solution must work across multiple nodes without relying on node-local memory for enforcement. |
| TR-2 | Concurrency safety | The implementation must prevent race conditions under simultaneous requests. |
| TR-3 | Shared state coordination | A shared backend such as Redis is expected to support atomic operations and cross-node coordination. |
| TR-4 | Deterministic behavior under load | The limiter must behave predictably under concurrent traffic and repeated requests. |
| TR-5 | Configurability | Quotas and policy parameters should be configurable rather than hardcoded. |
| TR-6 | Testability | The design must support unit, integration, concurrency, and load tests. |
| TR-7 | Fault tolerance | Behavior should be defined when the shared state store is slow, unavailable, or inconsistent. |
| TR-8 | Auditability | The system should support enough logging or metadata to explain each decision. |

---

## 6. Non-Functional Requirements

| ID | Requirement | Why it matters |
|---|---|---|
| NFR-1 | Correctness | Incorrect rate limiting is worse than no rate limiting. |
| NFR-2 | Low latency | Enforcement should introduce minimal added delay to each request. |
| NFR-3 | Reliability | The system should continue to provide a defensible outcome under partial failure. |
| NFR-4 | Scalability | The design should remain viable as traffic grows. |
| NFR-5 | Maintainability | The architecture should be understandable and explainable to engineers and stakeholders. |
| NFR-6 | Observability | Engineers should be able to inspect and diagnose limiter decisions. |
| NFR-7 | Security | Quota state and policy decisions must be protected from tampering or accidental misuse. |
| NFR-8 | Operability | The system should be deployable and manageable in a production-like environment. |

---

## 7. Stakeholder Requirements

| Stakeholder | Objective | Concern | Implied Requirement |
|---|---|---|---|
| CTO | Protect the platform and enforce policy consistently. | Overuse, abuse, and policy drift. | Strict, centralized enforcement and clear decision logic. |
| Support Lead | Preserve customer experience and minimize false positives. | Customers should not be blocked unfairly or unexpectedly. | A policy that is understandable and not overly punitive. |
| Platform/Operations | Keep the system reliable and easy to operate. | Failure modes and operational overhead. | Clear alerts, metrics, and resilient behavior. |
| Engineering Team | Deliver a robust and maintainable solution. | Complexity, debugging, and implementation risk. | A design that is testable and explainable. |
| Business/Product | Support customer expectations and contractual quota commitments. | Both fairness and compliance matter. | A documented and justifiable policy. |

---

## 8. Hidden Requirements

| ID | Hidden Requirement | Why it matters |
|---|---|---|
| HR-1 | The system must be correct under concurrency, not just under sequential testing. | Distributed systems often fail at exactly this boundary. |
| HR-2 | The solution must be resilient to random request distribution across nodes. | A node-local counter will appear to work in isolation but fail in reality. |
| HR-3 | The policy must be explicit, not implicit. | Ambiguity around over-limit behavior is a major design risk. |
| HR-4 | The solution must be demonstrable with real traffic patterns. | The assignment expects evidence, not just abstract design. |
| HR-5 | The implementation must be honest about tradeoffs. | The decision document is part of the deliverable. |

---

## 9. Constraints

| ID | Constraint | Impact |
|---|---|---|
| C-1 | Three stateless application nodes | Enforcing quotas cannot rely on in-memory state local to one node. |
| C-2 | Load balancer distributes requests randomly | Requests from the same customer may hit different nodes unpredictably. |
| C-3 | Customer quotas are based on RPM | The solution must evaluate a time-based window accurately. |
| C-4 | The assignment explicitly requires a distributed solution | A single-process design would not satisfy the problem. |
| C-5 | The solution must include a load-testing harness | The implementation must support realistic traffic simulation. |
| C-6 | The project must include explicit decision documentation | The policy decision is part of the deliverable, not an afterthought. |

---

## 10. Risks

| ID | Risk | Potential Effect |
|---|---|---|
| R-1 | Race conditions under concurrent requests | Double-admission or over-allowing requests. |
| R-2 | Inconsistent shared state | Quotas may be exceeded unexpectedly. |
| R-3 | Overly strict policy | Customer frustration and support escalation. |
| R-4 | Overly lenient policy | Quota abuse and missed business protection. |
| R-5 | Complex implementation | Harder to debug, test, and operate. |
| R-6 | Weak load testing | The system may appear correct under light traffic but fail under real load. |

---

## 11. Assumptions

| ID | Assumption |
|---|---|
| A-1 | Each customer has a clearly defined quota. |
| A-2 | Quota enforcement is evaluated per customer and per time window. |
| A-3 | A shared store is available for coordination. |
| A-4 | A request should be denied once the configured quota is exhausted unless a softer policy is explicitly chosen. |
| A-5 | The assignment expects strict correctness over convenience. |

---

## 12. Unknowns

| ID | Unknown |
|---|---|
| U-1 | The exact quota values for each customer are not specified. |
| U-2 | The precise policy for burst traffic is not specified. |
| U-3 | The expected response behavior for over-limit requests is not fully specified. |
| U-4 | The acceptable system latency impact of distributed coordination is not fully specified. |
| U-5 | The level of operational observability expected by stakeholders is not fully defined. |

---

## 13. Open Questions

| ID | Open Question |
|---|---|
| OQ-1 | Should the solution enforce a hard stop once the quota is reached, or allow a brief grace period? |
| OQ-2 | How should Northwind’s repeated nightly overage be treated: as a customer issue, a policy issue, or a system issue? |
| OQ-3 | What is the expected user-visible behavior for blocked requests? |
| OQ-4 | What level of instrumentation is required for operations and support? |
| OQ-5 | Should the design prioritize strict fairness, strict compliance, or better customer experience? |

---

## 14. Success Criteria

| ID | Success Criterion |
|---|---|
| SC-1 | The system enforces quotas correctly across all three nodes under concurrent traffic. |
| SC-2 | The limiter never allows a customer to exceed its stated quota due to race conditions or inconsistent state. |
| SC-3 | The load harness clearly demonstrates boundary behavior at the quota limit. |
| SC-4 | The project includes documentation that explains the chosen policy and the reasoning behind it. |
| SC-5 | The design is understandable, testable, and operationally reasonable. |

---

## 15. Five Biggest Engineering Challenges

1. Achieving correctness under distributed concurrency.
   The hardest problem is not counting requests; it is making sure the count is correct when several requests race across multiple nodes.

2. Preventing quota bypass through random load balancing.
   A request that lands on a different node must still be counted against the same customer quota.

3. Choosing and defending the policy for over-limit behavior.
   The Northwind case forces a business and engineering decision that must be explicit and justified.

4. Designing a solution that is simple enough to reason about but robust enough for production.
   The system must be understandable to engineers and support staff, not just technically correct in theory.

5. Building trustworthy evidence through testing and load generation.
   The assignment requires more than a plausible design; it requires a demonstrable implementation with boundary-case proof.

---

## 16. Summary

This project is fundamentally a distributed systems correctness problem wrapped in a business-policy challenge. The core requirement is to enforce customer quotas reliably across multiple nodes, while also making the policy explicit and defendable in the face of competing stakeholder priorities.

---

## 17. Stakeholder Conflict Review and Reassessment

### A. Challenge to the earlier recommendation

A skeptical senior engineer could reasonably argue that a strict hard-cap policy is too blunt for a real product environment. Their concern would be that a quota system with no flexibility can create unnecessary support load, customer friction, and operational noise, especially when a customer is only slightly over the limit or when the overage is temporary.

That criticism is valid. In practice, some systems use throttling, grace windows, or burst tolerance to soften the impact while still preserving the intent of the quota.

### B. The counterargument in favor of strict enforcement

The strongest argument for the original recommendation is that the assignment is explicitly testing distributed correctness and policy enforcement. If the system allows over-limit traffic too easily, then the limiter becomes less trustworthy and less defensible. A strict policy is easier to explain, easier to test, and easier to audit.

In other words, the strict model protects the core requirement: a customer should not exceed the stated quota because of race conditions, node randomness, or permissive policy handling.

### C. The case for a hybrid policy

The strongest alternative argument is that the product may need a hybrid approach:

- enforce the quota rigorously under ordinary conditions,
- but allow a small burst or short grace window for exceptional cases,
- and make that behavior configurable and explicit.

This approach can reduce customer pain while preserving the overall integrity of the quota system.

### D. Why I still prefer the strict recommendation

I would not change the recommendation. The reason is that the assignment is not primarily asking for the most customer-friendly behavior. It is asking for a distributed limiter that is correct, defensible, and demonstrably enforceable under concurrency.

A hybrid or soft-throttling model introduces additional policy complexity and makes the boundary behavior harder to prove. That creates a larger risk of implementation ambiguity and weaker evaluation outcomes.

### E. Conditions under which the recommendation would change

The recommendation would change if the stakeholders explicitly stated that:

1. quotas are soft operational guidelines rather than hard business limits,
2. a small burst allowance is required for customer experience,
3. the system must optimize for continuity over strictness,
4. or the business explicitly wants a throttling interface rather than a hard deny.

In those cases, a hybrid policy would become more appropriate.

### F. Final position

The strict hard-cap policy remains the best recommendation for this assignment because it maximizes correctness, clarity, and auditability. It is the most appropriate default when the primary requirement is to prove that distributed enforcement works and that customers cannot bypass the quota under load.

---

## 18. Phase 3: System Architecture

### 18.1 Architectural goal

The architecture must satisfy three simultaneous goals:

1. Enforce quotas correctly across all nodes.
2. Keep the enforcement logic centralized and shared.
3. Make the behavior observable and testable under load.

The architecture should be simple enough to explain but robust enough to support concurrency and failure scenarios.

---

### 18.2 Architecture alternatives considered

#### Option A: Per-node local limiter with shared state only for reporting

This design keeps the limiter logic on each node and uses a shared store only for metrics or logging.

Pros:
- Simpler to implement initially.
- Lower latency in the happy path.

Cons:
- Incorrect under concurrent and distributed traffic.
- Violates the core requirement of cross-node enforcement.
- Highly vulnerable to race conditions.

Verdict: not acceptable for this assignment.

#### Option B: Centralized limiter service

All requests are sent to a dedicated rate-limiting service, which makes the allow/deny decision and returns the result.

Pros:
- Very strong correctness.
- Easier to centralize policy and observability.
- Easier to reason about and test.

Cons:
- Adds latency and a new dependency.
- Creates a potential bottleneck.
- More infrastructure complexity than the assignment likely needs.

Verdict: strong design, but heavier than necessary for this exercise.

#### Option C: Distributed shared-state limiter using Redis

Each application node consults shared state in Redis before allowing a request.

Pros:
- Meets the distributed requirement.
- Keeps the system relatively simple.
- Allows atomic enforcement logic via Redis operations.
- Fits the assignment constraints well.

Cons:
- Requires careful handling of atomicity and failure cases.
- Adds dependency on Redis latency and availability.

Verdict: best fit for this assignment.

---

### 18.3 Recommended architecture

The recommended architecture is a distributed shared-state limiter using Redis as the coordination layer.

This design uses:

- a client sending requests,
- a load balancer distributing traffic randomly across three stateless application nodes,
- a middleware component on each node that checks quota state,
- Redis as the shared quota store,
- and a load harness to generate traffic and validate behavior.

---

### 18.4 ASCII architecture diagram

```text
+-----------------------+
|       Client          |
|   (test / API user)  |
+----------+------------+
           |
           v
+-----------------------+
|    Load Balancer      |
|  random distribution  |
+----------+------------+
           |
      +----+----+----+
      |    |    |    |
      v    v    v
+------+ +------+ +------+
| Node 1 | | Node 2 | | Node 3 |
| App    | | App    | | App    |
| +     | | +      | | +      |
| Middleware | | Middleware | | Middleware |
+---+----+ +---+----+ +---+----+
    |            |            |
    +------------+------------+
                 |
                 v
         +-------------------+
         |       Redis       |
         |  quota counters   |
         |  window state     |
         +-------------------+

+---------------------------+
| Logging / Metrics / Config |
|  structured logs          |
|  counters / histograms    |
|  quotas / policies        |
+---------------------------+
```

---

### 18.5 Component explanation

#### 1. Client

Purpose:
- Generates API traffic.
- Sends requests to the system under test.

Why it exists:
- The client is the source of the workload and the thing that proves the limiter works.

Responsibilities:
- Send requests with customer identity.
- Optionally vary request rate and concurrency.
- Observe whether requests are allowed or denied.

#### 2. Load Balancer

Purpose:
- Distribute incoming requests across the three application nodes.

Why it exists:
- The assignment explicitly requires random distribution across stateless nodes.
- This creates the distributed scenario the limiter must handle.

Responsibilities:
- Route requests to any node.
- Avoid sticky sessions unless explicitly desired.
- Preserve the randomness needed to exercise the distributed logic.

#### 3. Three Stateless Nodes

Purpose:
- Host the application logic and the limiter middleware.

Why it exists:
- The assignment requires three stateless instances that can receive traffic independently.

Responsibilities:
- Accept incoming requests.
- Invoke the rate-limiter middleware.
- Forward allowed requests to downstream application behavior.
- Return a response to the client.

Why “stateless” matters:
- Each node must not depend on local memory for quota enforcement.
- This forces the design to use shared state.

#### 4. Rate Limiter Middleware

Purpose:
- Evaluate whether the incoming request should be allowed.

Why it exists:
- This is the core enforcement point.

Responsibilities:
- Read the customer identity from the request.
- Determine the current quota state from Redis.
- Make an atomic allow/deny decision.
- Record the outcome for metrics and logs.

Why this is placed in middleware:
- It centralizes the policy decision.
- It can be applied consistently across all nodes.
- It makes the architecture easier to reason about and test.

#### 5. Redis

Purpose:
- Provide shared, cross-node state for quota counters and window tracking.

Why it exists:
- The stateless nodes cannot enforce quotas correctly using local memory alone.
- Redis provides a common source of truth.

Responsibilities:
- Store per-customer counters for the current window.
- Expire counters when the window rolls over.
- Support atomic operations for allow/deny decisions.
- Provide a place for debugging and observability.

Why Redis is a good fit:
- It is common in distributed systems.
- It supports fast key-value operations.
- It is suitable for this kind of quota enforcement problem.

#### 6. Configuration

Purpose:
- Externalize quotas and policy settings.

Why it exists:
- The system should not hardcode customer limits or policy decisions.

Responsibilities:
- Define per-customer quota values.
- Define window size and policy settings.
- Support environment-based or file-based configuration.

#### 7. Logging

Purpose:
- Record what happened for each request.

Why it exists:
- Logging is needed for debugging, traceability, and support.

Responsibilities:
- Log allow/deny outcomes.
- Capture customer ID, request ID, node ID, and policy reason.
- Record errors and failure events.

#### 8. Metrics

Purpose:
- Provide operational visibility.

Why it exists:
- The assignment requires boundary behavior and engineering clarity.

Responsibilities:
- Count allowed and denied requests.
- Track latency of the limiter decision.
- Record Redis errors and fallback behavior.
- Surface quota saturation events.

#### 9. Load Harness

Purpose:
- Generate traffic to validate the system.

Why it exists:
- The assignment explicitly requires a load-testing harness.

Responsibilities:
- Send concurrent requests to the system.
- Apply controlled rates and burst patterns.
- Report how many requests were allowed and denied.
- Demonstrate boundary behavior around the quota.

---

### 18.6 Interaction flow

#### Normal request path

1. The client sends a request to the load balancer.
2. The load balancer forwards the request to one of the three nodes.
3. The node’s middleware inspects the customer identity and quota policy.
4. The middleware checks or updates the shared state in Redis.
5. Redis returns an allow or deny decision.
6. The node either processes the request or returns a rejection response.
7. The decision is logged and counted in metrics.

#### Failure path

1. The middleware attempts to consult Redis.
2. Redis is slow, unavailable, or returns an error.
3. The middleware uses the configured degraded-mode policy.
4. The node logs the failure and records an error metric.
5. The client receives a predictable response.

---

### 18.7 Why this architecture fits the assignment

This architecture is the best fit because it is:

- distributed,
- simple enough to explain,
- consistent with the stateless-node constraint,
- and aligned with the requirement to use shared state for correctness.

It also makes the later implementation easier because the limiter decision point is cleanly isolated and observable.

---

### 18.8 Final recommendation

I recommend the distributed shared-state architecture using Redis-backed atomic quota checks.

This is the strongest choice because it directly satisfies the assignment’s hardest constraint: requests must be enforced consistently even when they are served by different nodes and arrive concurrently.

---

## 18.9 Architecture review: weaknesses and improvements

### A. Bottlenecks

| Area | Potential bottleneck | Why it matters |
|---|---|---|
| Redis | Every allow/deny decision depends on Redis availability and latency. | Under heavy traffic, Redis can become the limiting factor. |
| Load balancer | If the balancer is uneven or poorly configured, one node may receive disproportionate traffic. | This can create hot spots and skewed enforcement behavior. |
| Middleware execution path | Additional checks add latency to every request. | The limiter must not become the dominant cost in the request path. |

### B. Single points of failure

| Component | Risk | Impact |
|---|---|---|
| Redis | Central shared-state dependency. | If Redis fails, quota enforcement becomes unreliable or unavailable. |
| Load balancer | If it fails or misroutes traffic, the system may become uneven or unavailable. | Traffic distribution and health checks become compromised. |
| Configuration service or config file | If policy config is unavailable, the system may enforce the wrong defaults. | Quotas may be misapplied or denied unexpectedly. |

### C. Scalability issues

| Issue | Concern |
|---|---|
| Redis throughput | A single Redis instance may not scale well under very high request rates. |
| Window expiration | Large numbers of keys or counters can create memory churn and cleanup overhead. |
| Cross-node coordination | Atomic checks increase coordination overhead as node count grows. |
| Metrics volume | Logging every request may become expensive and noisy at scale. |

### D. Security concerns

| Concern | Why it matters |
|---|---|
| Customer identity spoofing | If the client can forge or misrepresent the customer identity, quotas can be bypassed. |
| Redis exposure | If Redis is not properly secured, quota state could be tampered with. |
| Sensitive telemetry | Logs and metrics may expose customer usage patterns or sensitive business data. |
| Configuration leakage | Quota policy values should not be exposed casually to unauthorized users. |

### E. Operational concerns

| Concern | Why it matters |
|---|---|
| Degraded-mode behavior | The system needs a clear policy when Redis is unavailable. |
| Drift between nodes | If configuration differs across nodes, the enforcement outcome may vary. |
| Failure observability | Operators need to know whether denials are due to policy, infrastructure, or configuration. |
| Rollout risk | A change to the limiter logic can affect many requests at once. |

### F. Monitoring gaps

| Gap | Why it matters |
|---|---|
| No per-customer decision metrics | It is hard to debug quota behavior without per-customer counters. |
| No saturation alerts | Operators need to know when customers are repeatedly hitting the limit. |
| No dependency health metrics | Redis latency and error rate are essential for diagnosis. |
| No request-trace correlation | It is difficult to investigate a denied request without request IDs and correlated logs. |

### G. Suggested improvements

1. Use Redis replication or a managed Redis cluster for higher availability.
2. Add a clear degraded-mode policy for Redis outages, such as fail-open with a warning or fail-closed with a circuit breaker.
3. Use a dedicated request ID and correlation ID in logs and metrics.
4. Add per-customer metrics and dashboards for allowed, denied, and throttled requests.
5. Separate configuration from code and validate configuration centrally.
6. Protect the limiter with authentication and authorization boundaries around the customer identity source.
7. Add rate-limit decision reasons to logs, such as quota-exhausted, window-reset, or redis-error.
8. Consider a more advanced state model later, such as a sliding window or hybrid policy, if the product requirement changes.
9. Use sampling for high-volume logging to reduce cost and noise.
10. Add load-test simulations that explicitly test Redis latency spikes and node failures.

---

## 19. Phase 4: Algorithm Selection

### 19.1 Objective

The algorithm must enforce customer quotas accurately across three nodes, under concurrency, while remaining understandable and producible. The selection should reflect both the distributed architecture and the earlier policy decision: strict enforcement is the default.

---

### 19.2 Algorithm options

#### 1. Fixed Window

Definition:
- Count requests within a fixed time period, such as a one-minute bucket.

Fairness:
- Moderate.
- Traffic can spike heavily near the boundary of the window.

Performance:
- Very good.
- Cheap to compute and cheap to store.

Memory:
- Low.

Burst handling:
- Poor.
- A burst at the end of one window can be followed by a quiet period at the start of the next.

Distributed systems:
- Straightforward.
- Can be implemented using atomic increments and window keys.

Complexity:
- Low.

Production usage:
- Common for simple quotas.

Failure cases:
- Boundary spikes can cause “burstiness” and perceived unfairness.

Pros:
- Simple and fast.
- Easy to reason about.
- Easy to implement correctly.

Cons:
- Can allow a customer to make a large burst at the window boundary.
- Less smooth than a rolling policy.

---

#### 2. Sliding Window

Definition:
- Track requests over a rolling time interval rather than a fixed calendar minute.

Fairness:
- High.
- Smoother than fixed window because it avoids hard resets.

Performance:
- Moderate to high.
- More expensive because the system must track timestamps or a rolling log.

Memory:
- Moderate to high.
- Especially if the system stores many timestamps per customer.

Burst handling:
- Better than fixed window.
- Allows more even request pacing.

Distributed systems:
- More complex.
- Requires careful coordination and potentially more state.

Complexity:
- Medium to high.

Production usage:
- Used when smoother enforcement is important.

Failure cases:
- Memory growth and timestamp cleanup can become expensive.
- Distributed implementations can become more complex under high load.

Pros:
- Fairer than fixed window.
- Better at preventing sharp bursts.

Cons:
- More memory-intensive.
- More state to maintain and purge.

---

#### 3. Token Bucket

Definition:
- Maintain a bucket of tokens that refills over time. Each request consumes one token.

Fairness:
- Good.
- Smooths traffic and makes short bursts possible without sacrificing long-run rate control.

Performance:
- Very good.
- Usually efficient and simple in practice.

Memory:
- Low.

Burst handling:
- Excellent.
- Allows short bursts while still enforcing average rate.

Distributed systems:
- Good.
- Fits well with a shared state store when implemented atomically.

Complexity:
- Medium.

Production usage:
- Very common in production rate limiting.

Failure cases:
- If the bucket is not updated atomically, tokens can be over-consumed.
- A very large burst may still be possible if the bucket size is set too high.

Pros:
- Smooth enforcement.
- Good for handling bursty traffic.
- Well-understood operationally.

Cons:
- Slightly less strict than a hard cap on a fixed window.
- Requires tuning of bucket size and refill rate.

---

#### 4. Leaky Bucket

Definition:
- Requests enter a queue and are released at a steady rate.

Fairness:
- Good for smoothing traffic.
- Less suitable when immediate decisions are needed.

Performance:
- Moderate.
- Queueing adds latency and operational complexity.

Memory:
- Moderate.
- Queue state can grow under overload.

Burst handling:
- Good for smoothing but not ideal for immediate deny decisions.

Distributed systems:
- More complex.
- Queueing and backpressure become harder to manage in a distributed system.

Complexity:
- High.

Production usage:
- Common in traffic shaping and networking, less common as a direct API quota mechanism.

Failure cases:
- Queue buildup can lead to latency spikes and memory pressure.
- Not ideal for a strict per-request allow/deny policy.

Pros:
- Excellent traffic smoothing.
- Prevents sudden load spikes.

Cons:
- Adds latency and queueing.
- Less suitable for short, immediate quota decisions.

---

#### 5. Hybrid

Definition:
- Combine a strict baseline policy with a burst allowance or smoothing mechanism.

Fairness:
- Good to very good.
- Depends on the exact design.

Performance:
- Moderate.
- More logic than a simple algorithm.

Memory:
- Low to moderate.

Burst handling:
- Good.
- Can support both strictness and flexibility.

Distributed systems:
- Moderate.
- More complex but still feasible with shared state.

Complexity:
- High.

Production usage:
- Used when policy needs to balance strictness and customer experience.

Failure cases:
- More configuration and tuning complexity.
- Easier for the policy to drift or be misconfigured.

Pros:
- Flexible.
- Can satisfy both business and support concerns.

Cons:
- Harder to reason about.
- Harder to test and explain.
- More opportunity for misconfiguration.

---

### 19.3 Side-by-side comparison

| Algorithm | Fairness | Performance | Memory | Burst Handling | Distributed Systems | Complexity | Production Usage |
|---|---|---|---|---|---|---|---|
| Fixed Window | Medium | Excellent | Low | Poor | Good | Low | Very common |
| Sliding Window | High | Good | Medium/High | Good | Medium | Medium/High | Common |
| Token Bucket | Good | Excellent | Low | Excellent | Good | Medium | Very common |
| Leaky Bucket | Good | Moderate | Medium | Good | Medium/High | High | Common in traffic shaping |
| Hybrid | Good/Very Good | Moderate | Low/Medium | Good | Medium | High | Used when policy is nuanced |

---

### 19.4 Recommendation

The best algorithm for this prototype is a fixed-window shared counter with strict denial after the configured quota is exhausted.

### Why the shared counter is the best fit

1. It directly matches the stakeholder decision.
   The quota is treated as a hard platform-protection boundary. Once the count reaches the configured limit, the next request is denied.

2. It is simple to explain and audit.
   Reviewers can reason about the exact boundary: below quota is allowed, at quota is still valid for the admitted request, and above quota is rejected.

3. It is a practical fit for Redis-backed coordination.
   The state model is small: customer ID, usage count, and window expiry.

4. It keeps the prototype focused.
   A token bucket is a useful production pattern, but adding burst semantics would complicate the Northwind policy decision and weaken the hard-cap interpretation.

5. It leaves a clear upgrade path.
   If Product later decides quotas should allow bursts, the local token-bucket reference can guide a future Redis-backed implementation.

---

### 19.5 Why not the others?

#### Fixed Window
- Blunt at the window boundary, but acceptable because the chosen policy optimizes for strictness and explainability.
- Good for simple quotas and for demonstrating exact boundary behavior.

#### Sliding Window
- More accurate than fixed window, but it is heavier in memory and complexity.
- It is a strong candidate in a more sophisticated system, but the assignment favors clarity and implementation practicality.

#### Leaky Bucket
- Excellent for smoothing, but less suitable for immediate allow/deny decisions.
- It is more about shaping traffic than enforcing per-customer quotas directly.

#### Hybrid
- Powerful, but too complex for this assignment’s scope unless the stakeholders explicitly require nuanced behavior.
- It introduces extra policy tuning and makes the system harder to reason about.

---

### 19.6 Final position

For this assignment, I recommend the fixed-window shared counter as the primary distributed enforcement algorithm, with token bucket retained as a local reference and possible future evolution. That keeps the implementation aligned with the strict hard-deny stakeholder decision.

---

## 20. Phase 5: Distributed Coordination Design

### 20.1 Goal

The goal of distributed coordination is to ensure that all three application nodes make the same decision for the same customer quota, even when requests arrive at the same time and are routed to different nodes.

In other words, the system must behave as if there were a single shared decision point, even though the requests are physically handled by multiple nodes.

---

### 20.2 Shared State

#### What shared state means

Shared state is any data that multiple application nodes can read and update together. In this system, the relevant shared state is the customer’s current request count, the current time window, and the remaining token balance for that customer.

#### Why it is necessary

If each node kept its own local counter, the system would break under distributed traffic. One node could believe the customer still has quota left while another node has already consumed it.

#### What shared state must contain

| State | Purpose |
|---|---|
| Customer quota configuration | Defines the allowed rate |
| Current usage count or token balance | Tracks how much of the quota has been consumed |
| Window metadata | Tracks the active time window |
| Last update timestamp | Helps with expiration and reset logic |
| Decision outcome | Supports logging and observability |

---

### 20.3 Redis as the coordination layer

#### Why Redis is used

Redis is a good fit because it provides a fast, shared, in-memory data store with atomic operations. That makes it suitable for coordinating distributed rate-limit decisions.

#### What Redis provides

- a centralized view of quota state,
- fast key-value access,
- atomic operations for update-and-check logic,
- and a simple way for all three nodes to agree on the same state.

#### Redis role in the design

Redis is not just a cache. It is the coordination authority for the limiter.

#### Simple diagram

```text
+-----------+      +-----------+      +-----------+
| Node 1    | ---> |   Redis   | <--- | Node 2    |
| Middleware|      | Shared    |      | Middleware|
+-----------+      | State     |      +-----------+
                     +-----------+
                           ^
                           |
                     +-----------+
                     | Node 3    |
                     | Middleware|
                     +-----------+
```

---

### 20.4 Atomic operations

#### What an atomic operation is

An atomic operation is one that appears to happen as a single indivisible action. In this system, it means that the limiter should not read the customer’s quota, decide to allow the request, and then later update the counter in a way that can be interrupted by another node.

#### Why atomicity matters

Without atomicity, two nodes can both observe that the customer still has quota left and both admit the request, causing over-admission.

#### Example of the failure

Imagine quota is 3 requests per minute.

- Node 1 reads current count = 2.
- Node 2 reads current count = 2.
- Node 1 allows request and writes 3.
- Node 2 allows request and writes 3.

Result: the system allowed 4 requests, exceeding the policy.

#### What the system should do instead

The limiter should perform a single atomic check-and-update operation such as:

- check current usage,
- if below quota, increment and allow,
- otherwise deny.

This must happen in one logical step.

---

### 20.5 Race conditions

#### What a race condition is

A race condition occurs when multiple requests arrive simultaneously and the system’s outcome depends on timing rather than policy.

#### Why they are dangerous here

The assignment specifically requires correctness under concurrency. Race conditions are the most likely way to violate the quota.

#### Common race scenarios

1. Two nodes read the same counter at the same time.
2. A window expires while two requests are being processed.
3. A request is retried and counted twice.
4. Redis latency causes one node to act on stale state.

#### Preventing them

The design prevents race conditions by using:

- atomic updates,
- a single shared state source,
- and a clear policy around request identity and retries.

---

### 20.6 Lua scripts

#### Why Lua scripts matter

Lua scripts allow the limiter logic to run inside Redis itself. This is important because the whole allow/deny decision can be executed atomically without the application nodes competing with each other.

#### Why this is better than separate read/write operations

Without Lua, the design typically looks like this:

1. Node reads counter from Redis.
2. Node computes decision.
3. Node writes updated counter back to Redis.

That sequence is vulnerable to race conditions because another node can interleave between steps.

#### With Lua

The script performs the whole decision in one Redis execution:

- read counter,
- compare with quota,
- increment or deny,
- write result,
- return a single outcome.

#### Diagram

```text
Node 1 / Node 2 / Node 3
          | 
          v
     +-----------+
     | Lua Script |
     | - read     |
     | - compare  |
     | - update   |
     | - return   |
     +-----------+
          |
          v
        Redis
```

#### Why Lua is attractive here

- Strong correctness properties.
- Reduced network round trips.
- Better protection against race conditions.

#### Tradeoff

- Slightly more complex to write and debug.
- The logic becomes embedded in Redis, which can be harder to maintain if overused.

---

### 20.7 Clock synchronization

#### Why clock issues matter

The limiter uses time-based windows, so the system depends on clocks. If the nodes or Redis do not have reasonably synchronized time, the window boundaries can drift.

#### What can go wrong

- A request near the window boundary may be counted in the wrong window.
- A reset may happen earlier or later than intended.
- Different nodes may disagree on the current window.

#### Practical approach

The design should assume:

- a reasonably synchronized system clock,
- and a single authoritative time source for the window logic.

#### Production note

In production, clock skew should be minimized with NTP or equivalent services. For this assignment, the important point is that the design must not assume perfect clock alignment across all components.

---

### 20.8 Distributed consistency

#### What consistency means here

Consistency means that every node sees the same quota state at the moment of decision.

#### What the system is trying to guarantee

The system seeks a form of strong enough consistency for quota enforcement:

- if a request is allowed, it should count toward the quota,
- if denied, it should not be counted,
- and all nodes should agree on the outcome.

#### Why this is hard

Distributed systems are almost always trading off between:

- availability,
- latency,
- and consistency.

For this assignment, correctness is prioritized, so the design uses a shared state store and atomic operations rather than local memory or loose coordination.

---

### 20.9 Failure recovery

#### What can fail

- Redis can become slow or unavailable.
- A node can crash mid-request.
- A request may be retried after a timeout.
- The time window may roll over during high traffic.

#### How the design should respond

The system should define a recovery behavior explicitly.

#### Recommended policy

- If Redis is unavailable, the system should not silently allow requests without a clear policy.
- The system should either:
  - fail closed and deny the request, or
  - fail open only if explicitly approved by policy and clearly logged.

For this assignment, the safer default is fail closed, because the goal is correctness and strict enforcement.

#### Recovery considerations

- Reset counters at window boundaries.
- Clear stale state appropriately.
- Use logs and metrics to detect abnormal patterns after failures.

---

### 20.10 Horizontal scaling

#### What horizontal scaling means

Horizontal scaling means adding more application nodes to handle more traffic.

#### Why it matters

The assignment requires three nodes today, but the design should not be tightly coupled to that number.

#### How the design scales

- The application nodes remain stateless.
- Redis handles the shared state.
- The limiter logic remains in middleware.
- Additional nodes can be added without changing the basic model.

#### Diagram

```text
Client --> Load Balancer --> Node 1
                           --> Node 2
                           --> Node 3
                           --> Node 4
                           --> Node 5

All nodes --> Redis (shared quota state)
```

#### Scaling limitations

Redis can become a bottleneck if traffic grows too much, so a production system would eventually need clustering or a more specialized coordination layer.

---

### 20.11 Final design principle

The system should be designed around one central rule:

No node should make a quota decision independently.

Every decision should be derived from shared state through an atomic, coordinated operation.

---

## 21. Phase 6: Implementation Roadmap

### 21.1 Delivery strategy

The implementation should proceed in milestones so that correctness is verified incrementally. Each milestone builds on the previous one and ends with a tangible output.

---

### Milestone 1: Project skeleton and configuration

#### Goal
Create the scaffolding for the limiter, configuration, logging, and test harness.

#### Files
- README.md
- DECISIONS.md
- requirements.txt or equivalent dependency manifest
- config.yaml or config.json
- app/__init__.py
- app/config.py
- app/logger.py
- app/models.py

#### Classes
- Config
- LoggerAdapter
- RateLimitPolicy

#### Responsibilities
- Define the project structure.
- Externalize policy settings.
- Establish logging conventions.
- Provide placeholder models for customer and request context.

#### APIs
- None yet, or configuration loading helpers.

#### Tests
- Configuration loads successfully.
- Default policy values are valid.
- Logging initialization works without errors.

#### Expected Output
A runnable project skeleton with documented configuration and logging setup.

#### Estimated Time
2–3 days

---

### Milestone 2: In-memory reference limiter

#### Goal
Implement a single-process version of the limiter to validate the algorithm before distributed coordination is introduced.

#### Files
- app/rate_limiter.py
- app/algorithms/token_bucket.py
- tests/test_token_bucket.py

#### Classes
- TokenBucketLimiter
- TokenBucket

#### Responsibilities
- Implement the chosen algorithm in a simple, testable form.
- Enforce per-customer quota decisions locally.
- Produce allow/deny outcomes for a single process.

#### APIs
- allow_request(customer_id: str) -> bool
- get_state(customer_id: str) -> dict

#### Tests
- Allowed requests below quota succeed.
- Requests above quota are denied.
- Bucket refills over time.
- Boundary behavior is correct.

#### Expected Output
A working local limiter with tests proving the algorithm.

#### Estimated Time
2–3 days

---

### Milestone 3: Redis-backed shared state

#### Goal
Introduce Redis as the shared coordination layer for quotas.

#### Files
- app/storage/redis_store.py
- app/storage/interfaces.py
- tests/test_redis_store.py

#### Classes
- RedisQuotaStore
- QuotaStoreInterface

#### Responsibilities
- Connect to Redis.
- Store per-customer quota state.
- Support atomic update and check semantics.
- Provide a clean storage abstraction.

#### APIs
- get_customer_state(customer_id)
- increment_customer_usage(customer_id, quota)
- reset_customer_window(customer_id)

#### Tests
- Redis connection succeeds.
- State is stored and retrieved correctly.
- Window reset works.
- Store handles missing customers.

#### Expected Output
A shared-state abstraction that can be used by the limiter.

#### Estimated Time
2–3 days

---

### Milestone 4: Distributed limiter middleware

#### Goal
Create the middleware that runs on each application node and makes the allow/deny decision using shared Redis state.

#### Files
- app/middleware/limiter_middleware.py
- app/services/rate_limit_service.py
- tests/test_middleware.py

#### Classes
- RateLimitMiddleware
- RateLimitService

#### Responsibilities
- Read customer identity from requests.
- Call the shared store.
- Decide whether the request is allowed.
- Return a structured decision result.

#### APIs
- evaluate_request(request_context) -> DecisionResult

#### Tests
- Requests below quota are allowed.
- Requests above quota are denied.
- Middleware returns the correct decision reason.
- Middleware handles missing identity safely.

#### Expected Output
A reusable middleware component that can be applied on each node.

#### Estimated Time
2–3 days

---

### Milestone 5: Node integration and request flow

#### Goal
Integrate the middleware into the application nodes so requests pass through the limiter end to end.

#### Files
- app/nodes/node_app.py
- app/nodes/handler.py
- tests/test_node_integration.py

#### Classes
- ApplicationHandler
- NodeRuntime

#### Responsibilities
- Wire the middleware into the request path.
- Ensure each node uses the same shared policy.
- Return a consistent response for allowed and denied requests.

#### APIs
- POST /requests or equivalent request entrypoint

#### Tests
- A request through Node 1 is enforced correctly.
- A request through Node 2 is enforced correctly.
- A request through Node 3 is enforced correctly.
- Denied requests return the expected response.

#### Expected Output
A single end-to-end request flow that uses the distributed limiter.

#### Estimated Time
2–3 days

---

### Milestone 6: Load harness and traffic generation

#### Goal
Build a load-testing harness that sends concurrent traffic and demonstrates the limiter behavior at the boundary.

#### Files
- harness/load_harness.py
- harness/scenarios.py
- tests/test_harness.py

#### Classes
- LoadHarness
- ScenarioConfig
- TrafficGenerator

#### Responsibilities
- Generate traffic with configurable concurrency and rate.
- Simulate multiple customers and burst patterns.
- Report allowed versus denied counts.
- Highlight quota boundary behavior.

#### APIs
- run_scenario(config) -> report

#### Tests
- Harness executes a small controlled scenario.
- Report includes allowed and denied counters.
- Boundary scenario produces expected totals.

#### Expected Output
A harness that proves the distributed limiter behaves correctly under load.

#### Estimated Time
3–4 days

---

### Milestone 7: Observability and documentation

#### Goal
Add logging, metrics, and decision documentation so the system is understandable in operation.

#### Files
- app/observability/metrics.py
- app/observability/logging.py
- docs/architecture.md
- docs/DECISIONS.md

#### Classes
- MetricsCollector
- DecisionLogger

#### Responsibilities
- Record allow/deny decisions.
- Emit counters and latency metrics.
- Write clear operational documentation.
- Document the stakeholder decision and policy rationale.

#### APIs
- record_decision(customer_id, outcome, reason)
- record_metric(name, value)

#### Tests
- Metrics are emitted for allowed and denied requests.
- Logs include request identifiers and decision reasons.
- Documentation is present and consistent with implementation.

#### Expected Output
A system that is observable, supportable, and explainable.

#### Estimated Time
2–3 days

---

### Milestone 8: Failure handling and resilience testing

#### Goal
Validate the system under Redis latency, Redis failure, and request retries.

#### Files
- tests/test_failure_modes.py
- tests/test_retries.py
- app/failure_policy.py

#### Classes
- FailurePolicy
- RetryStrategy

#### Responsibilities
- Define graceful behavior for dependency failures.
- Protect against duplicate counting or double-admission.
- Ensure the system returns a predictable outcome under abnormal conditions.

#### APIs
- handle_dependency_failure(context)

#### Tests
- Redis outage causes a documented, safe outcome.
- Retries do not double count.
- Timeout handling is predictable.

#### Expected Output
A resilient limiter that behaves safely when the shared state layer is stressed.

#### Estimated Time
2–3 days

---

### Milestone 9: Final integration and review

#### Goal
Perform end-to-end verification and produce the final deliverables.

#### Files
- README.md
- DECISIONS.md
- docs/architecture.md
- tests/integration/test_end_to_end.py

#### Classes
- None new; integration validation layer

#### Responsibilities
- Run the full suite.
- Review design decisions.
- Confirm that all deliverables are coherent and complete.

#### APIs
- End-to-end request validation flow

#### Tests
- Full end-to-end execution with multiple nodes.
- Load test demonstrates correct limit behavior.
- Documentation matches implementation.

#### Expected Output
A complete, reviewed, and demonstrable solution.

#### Estimated Time
2–3 days

---

### 21.2 Summary roadmap

| Milestone | Focus | Primary risk |
|---|---|---|
| 1 | Skeleton and config | Under-specifying the policy |
| 2 | Local algorithm | Incorrect token logic |
| 3 | Redis integration | Weak atomicity design |
| 4 | Middleware | Policy misapplication |
| 5 | Node integration | Inconsistent request path |
| 6 | Load harness | Incomplete boundary testing |
| 7 | Observability | Poor supportability |
| 8 | Failure handling | Unsafe degraded behavior |
| 9 | Final review | Missing documentation or weak verification |

---

### 21.3 Recommended sequencing

The roadmap should be executed in order because each milestone removes a specific uncertainty. The local algorithm must be correct before shared-state logic is introduced. The shared-state layer must be correct before node integration. The harness should come only after the limiter itself is trustworthy.

---

## 22. Proposed Project Folder Structure

### 22.1 Recommended structure

```text
relayapi-rate-limiter/
├── README.md
├── DECISIONS.md
├── requirements.txt
├── pyproject.toml
├── config/
│   └── default.yaml
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── logger.py
│   ├── models.py
│   ├── algorithms/
│   │   ├── __init__.py
│   │   └── token_bucket.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── interfaces.py
│   │   └── redis_store.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── limiter_middleware.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── rate_limit_service.py
│   ├── nodes/
│   │   ├── __init__.py
│   │   └── node_app.py
│   ├── observability/
│   │   ├── __init__.py
│   │   └── metrics.py
│   └── failure_policy.py
├── harness/
│   ├── __init__.py
│   ├── load_harness.py
│   └── scenarios.py
├── tests/
│   ├── __init__.py
│   ├── test_token_bucket.py
│   ├── test_redis_store.py
│   ├── test_middleware.py
│   ├── test_node_integration.py
│   ├── test_harness.py
│   ├── test_failure_modes.py
│   └── integration/
│       └── test_end_to_end.py
├── docs/
│   ├── architecture.md
│   └── operations.md
└── scripts/
    └── run_local_demo.sh
```

---

### 22.2 Folder explanations

#### 1. config/
Purpose:
- Hold configuration files for quotas, window size, Redis connection settings, and policy defaults.

Why it exists:
- Configuration should be externalized so the limiter can be tuned without changing application code.

Contents:
- default.yaml or similar.

---

#### 2. app/
Purpose:
- Contain the core application logic.

Why it exists:
- This keeps the implementation organized and separates business logic from infrastructure and tests.

Subfolders:
- algorithms/: rate-limiting algorithm implementations.
- storage/: Redis and other persistence abstractions.
- middleware/: request interception logic.
- services/: high-level service layer for the limiter.
- nodes/: node-specific application entrypoints.
- observability/: logging and metrics.

---

#### 3. harness/
Purpose:
- Hold the load generator and traffic scenarios for validation.

Why it exists:
- The harness is a distinct concern from the application runtime and should not be mixed into core logic.

Responsibilities:
- Generate traffic,
- simulate concurrency,
- measure outcomes,
- and report boundary behavior.

---

#### 4. tests/
Purpose:
- Contain unit, integration, concurrency, and load tests.

Why it exists:
- The project needs a strong verification story, especially for distributed correctness.

Structure:
- unit tests near the logic they validate,
- integration tests for cross-component behavior,
- and an end-to-end folder for full-system validation.

---

#### 5. docs/
Purpose:
- Store architecture, operations, and decisions documentation.

Why it exists:
- The assignment explicitly requires documentation and a clear decision record.

Contents:
- architecture.md
- operations.md
- and the earlier decision document.

---

#### 6. scripts/
Purpose:
- Hold helper scripts for local demo, startup, or test execution.

Why it exists:
- Useful for running the system locally without needing manual commands each time.

---

## 23. File-by-file explanation

### Root files

#### README.md
Purpose:
- High-level overview of the project, how to run it, and what it does.

Why it matters:
- It is the first point of entry for reviewers and engineers.

#### DECISIONS.md
Purpose:
- Record the stakeholder conflict resolution and the chosen policy.

Why it matters:
- The assignment explicitly asks for an honest decision document.

#### requirements.txt
Purpose:
- Declare Python dependencies.

Why it matters:
- Keeps the environment reproducible.

#### pyproject.toml
Purpose:
- Define packaging metadata, tooling, and test configuration.

Why it matters:
- Useful for modern Python development and consistent project setup.

---

### Core application files

#### app/__init__.py
Purpose:
- Mark the directory as a Python package.

Why it matters:
- Enables clean imports across modules.

#### app/main.py
Purpose:
- Application entrypoint for local running or orchestration.

Why it matters:
- Keeps startup logic separate from the core limiter implementation.

#### app/config.py
Purpose:
- Load and validate configuration.

Why it matters:
- Keeps policy values external and testable.

#### app/logger.py
Purpose:
- Provide logging utilities.

Why it matters:
- Ensures logging is consistent across components.

#### app/models.py
Purpose:
- Define request context, customer identity, and decision result models.

Why it matters:
- Makes the codebase more explicit and easier to test.

---

### Algorithm layer

#### app/algorithms/token_bucket.py
Purpose:
- Implement the token bucket algorithm.

Why it matters:
- This is the core rate-limiting logic.

#### app/algorithms/__init__.py
Purpose:
- Export the algorithm implementation cleanly.

---

### Storage layer

#### app/storage/interfaces.py
Purpose:
- Define the storage contract for quota state.

Why it matters:
- Makes the limiter dependency-invertible and testable.

#### app/storage/redis_store.py
Purpose:
- Implement the shared-state storage using Redis.

Why it matters:
- This is where the distributed coordination is realized.

---

### Middleware and services

#### app/middleware/limiter_middleware.py
Purpose:
- Apply the rate-limiting decision at the request boundary.

Why it matters:
- This is the enforcement point for each node.

#### app/services/rate_limit_service.py
Purpose:
- Coordinate between the algorithm and the storage layer.

Why it matters:
- Keeps the business logic separate from the transport layer.

---

### Node layer

#### app/nodes/node_app.py
Purpose:
- Represent the application node runtime.

Why it matters:
- Makes it possible to model each of the three stateless nodes cleanly.

---

### Observability and resilience

#### app/observability/metrics.py
Purpose:
- Emit metrics for allowed, denied, and errored requests.

Why it matters:
- Critical for operations and debugging.

#### app/failure_policy.py
Purpose:
- Define how the system behaves when Redis or the shared state layer is unhealthy.

Why it matters:
- Protects the system from unsafe or unpredictable failure modes.

---

### Harness and tests

#### harness/load_harness.py
Purpose:
- Generate traffic and run scenarios.

Why it matters:
- Required to demonstrate correctness under load.

#### harness/scenarios.py
Purpose:
- Define benchmark scenarios such as burst, boundary, and failure cases.

Why it matters:
- Keeps the harness logic configurable and reusable.

#### tests/...
Purpose:
- Verify the limiter, Redis store, middleware, integration path, and failure behavior.

Why it matters:
- Essential for correctness and confidence under change.

---

## 24. Recommended Technology Stack

### 24.1 Recommended stack

- Python 3.11+
- FastAPI for the API/web layer
- Redis for shared state coordination
- pytest for testing
- pydantic for request/response models and config validation
- structlog or standard logging for structured logs
- Prometheus client or OpenTelemetry for metrics
- Docker Compose for local simulation of the three nodes and Redis

### 24.2 Why this stack is the best fit

#### Python
Why:
- The assignment is being developed in Python.
- Python is suitable for rapid, readable implementation.
- It is excellent for building a clean service-oriented prototype and a test harness.

Advantages:
- Readable and approachable.
- Strong ecosystem for networking, testing, and concurrency.

Tradeoff:
- Not the highest-performance choice for extreme throughput, but appropriate for this assignment.

#### FastAPI
Why:
- It provides a simple web framework for creating request entrypoints.
- It integrates well with pydantic and modern Python practices.

Advantages:
- Fast to develop.
- Strong validation and dependency injection support.

Tradeoff:
- A lighter framework could also work, but FastAPI is a strong balance of clarity and productivity.

#### Redis
Why:
- It is the most appropriate shared-state layer for the chosen architecture.

Advantages:
- Fast,
- widely understood,
- supports atomic operations,
- and fits the distributed coordination requirement.

Tradeoff:
- Adds an operational dependency that must be monitored.

#### pytest
Why:
- It is the standard test framework in the Python ecosystem.
- It supports unit, integration, and concurrency-oriented testing well.

Advantages:
- Very flexible.
- Excellent ecosystem support.

#### pydantic
Why:
- Useful for validating request structure and configuration.

Advantages:
- Reduces runtime errors.
- Improves clarity of models.

#### Docker Compose
Why:
- It allows the three nodes and Redis to be simulated locally in a single environment.

Advantages:
- Excellent for development and demo scenarios.
- Makes the architecture understandable and reproducible.

---

## 25. Final recommendation

The recommended project structure is a modular Python service with a clear separation between:

- core algorithm logic,
- shared-state storage,
- middleware enforcement,
- node-level entrypoints,
- and load-testing infrastructure.

That organization is appropriate because the assignment is not simply about writing a rate limiter; it is about demonstrating engineering discipline, correctness under concurrency, and a production-minded design.
