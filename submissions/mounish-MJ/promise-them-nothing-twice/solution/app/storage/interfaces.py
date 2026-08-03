from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class QuotaStoreInterface(ABC):
    """Abstract interface for shared quota state storage."""

    @abstractmethod
    def get_customer_state(self, customer_id: str) -> dict[str, Any]:
        """Return the current shared state for a customer, or {} if absent."""

    @abstractmethod
    def increment_customer_usage(self, customer_id: str, quota: int, window_seconds: int | None = None) -> dict[str, Any]:
        """Increment the customer's usage count and return the resulting state."""

    @abstractmethod
    def reserve_quota(self, customer_id: str, quota: int, limit: int, window_seconds: int | None = None) -> tuple[bool, dict[str, Any]]:
        """Reserve capacity and return decision metadata.

        Stores should include usage in returned metadata, and retry_after when
        a reservation is denied and a reset time is known.
        """

    @abstractmethod
    def reset_customer_window(self, customer_id: str) -> None:
        """Reset the customer's window state for the next quota period."""
