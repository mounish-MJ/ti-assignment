from __future__ import annotations

from prometheus_client import Counter, Histogram

# Request counter
RATE_LIMIT_REQUESTS = Counter(
    "rate_limit_requests_total",
    "Total number of rate limiting requests processed",
    ["customer_id", "status", "node_id", "policy"],
)

# Store error counter
STORE_ERRORS = Counter(
    "rate_limit_store_errors_total",
    "Total number of storage layer exceptions encountered",
    ["operation"],
)

# Request latency histogram
EVALUATION_LATENCY = Histogram(
    "rate_limit_evaluation_duration_seconds",
    "Time spent performing rate limit evaluations",
    buckets=(0.001, 0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)
