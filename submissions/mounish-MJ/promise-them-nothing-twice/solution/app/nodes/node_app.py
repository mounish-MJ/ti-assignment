from __future__ import annotations

from typing import Any

from app.middleware.limiter_middleware import RateLimitMiddleware
from app.models import RequestContext


class NodeRuntime:
    """A simple node runtime that routes requests through the shared limiter.

    This milestone focuses on the request flow rather than a web framework.
    The runtime accepts a payload-like dictionary and translates it into the
    structured request context used by the middleware.
    """

    def __init__(self, middleware: RateLimitMiddleware, node_id: str) -> None:
        self.middleware = middleware
        self.node_id = node_id

    def handle_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Handle an incoming request payload and return a response dictionary."""

        request_context = RequestContext(
            customer_id=str(payload.get("customer_id", "")),
            request_id=str(payload.get("request_id", "req-unknown")),
            node_id=self.node_id,
        )

        decision = self.middleware.evaluate(request_context)

        response = {
            "status": "accepted" if decision.allowed else "rejected",
            "customer_id": decision.customer_id,
            "request_id": decision.request_id,
            "node_id": decision.node_id,
            "reason": decision.reason,
        }

        if decision.retry_after is not None:
            response["retry_after"] = decision.retry_after

        if decision.limit is not None:
            response["limit"] = decision.limit
        if decision.remaining is not None:
            response["remaining"] = decision.remaining
        if decision.policy is not None:
            response["policy"] = decision.policy
        response["exception_applied"] = decision.exception_applied

        return response
