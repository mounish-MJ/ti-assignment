from __future__ import annotations

from app.logger import get_logger

logger = get_logger(__name__)


class FailurePolicy:
    """Policy that defines how the rate limiter handles failures of its shared state store."""

    def __init__(self, strict_mode: bool = True) -> None:
        self.strict_mode = strict_mode

    def handle_store_failure(self, customer_id: str, exception: Exception) -> tuple[bool, dict]:
        """Decide the allow/deny outcome when the database/store raises an exception.

        By default:
        - If strict_mode is True, we fail-open (allow request) but flag the degradation,
          since we want to prioritize customer uptime when the limiter system is degraded.
        """
        logger.error(
            "state_store_failure",
            extra={
                "customer_id": customer_id,
                "error": str(exception),
                "action": "degraded_allow",
            },
        )
        # Fail-open: allow request, set usage to 0, mark exception as True
        return True, {
            "customer_id": customer_id,
            "usage": 0,
            "exception_applied": True,
            "error_detail": str(exception),
        }
