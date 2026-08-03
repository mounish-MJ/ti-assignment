from __future__ import annotations

from app.models import DecisionResult, RequestContext
from app.services.rate_limit_service import RateLimitService


class RateLimitMiddleware:
    """Thin middleware wrapper around the rate-limit service.

    The middleware keeps the public entry point simple for later integration with
    web frameworks or request pipelines.
    """

    def __init__(self, service: RateLimitService) -> None:
        self.service = service

    def evaluate(self, request_context: RequestContext) -> DecisionResult:
        """Evaluate a request context and return a structured decision."""

        return self.service.evaluate_request(request_context)
