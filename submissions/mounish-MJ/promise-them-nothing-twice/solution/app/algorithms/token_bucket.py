from __future__ import annotations

import time
from collections import defaultdict


class TokenBucketLimiter:
    """A simple in-memory token bucket limiter for a single process.

    This implementation is intentionally simple and is meant to be the reference
    behavior for later distributed milestones.
    """

    def __init__(self, capacity: int, refill_rate: float) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens: dict[str, float] = defaultdict(float)
        self._last_refill: dict[str, float] = defaultdict(float)

    def _ensure_state(self, customer_id: str) -> None:
        if customer_id not in self._tokens:
            self._tokens[customer_id] = float(self.capacity)
            self._last_refill[customer_id] = time.monotonic()

    def refill(self, customer_id: str, elapsed_seconds: float | None = None) -> float:
        """Refill tokens for a customer based on elapsed time."""

        self._ensure_state(customer_id)
        now = time.monotonic()
        if elapsed_seconds is None:
            elapsed_seconds = now - self._last_refill[customer_id]

        self._last_refill[customer_id] = now
        new_tokens = min(self.capacity, self._tokens[customer_id] + elapsed_seconds * self.refill_rate)
        self._tokens[customer_id] = new_tokens
        return self._tokens[customer_id]

    def allow_request(self, customer_id: str) -> bool:
        """Return True if the request should be allowed, otherwise False."""

        self._ensure_state(customer_id)
        self.refill(customer_id)

        if self._tokens[customer_id] >= 1.0:
            self._tokens[customer_id] -= 1.0
            return True

        return False

    def get_state(self, customer_id: str) -> dict[str, float]:
        """Return the current token state for a customer."""

        self._ensure_state(customer_id)
        self.refill(customer_id)
        return {
            "tokens": self._tokens[customer_id],
            "capacity": float(self.capacity),
            "refill_rate": self.refill_rate,
        }
