from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class RequestContext:
    """Context associated with an incoming request."""

    customer_id: str
    request_id: str
    node_id: str


@dataclass(frozen=True)
class DecisionResult:
    """Outcome of a rate-limit evaluation."""

    allowed: bool
    reason: Literal["allowed", "quota_exceeded", "missing_customer_id"]
    customer_id: str
    request_id: str
    node_id: str
    retry_after: int | None = None
    limit: int | None = None
    remaining: int | None = None
    policy: str | None = None
    exception_applied: bool = False
