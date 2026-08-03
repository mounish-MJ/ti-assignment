from __future__ import annotations

import logging
from contextvars import ContextVar

# ContextVar storing the current request ID
_request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str | None) -> None:
    """Set the active request ID in the context local storage."""
    _request_id_ctx.set(request_id)


def get_request_id() -> str | None:
    """Retrieve the active request ID from context local storage."""
    return _request_id_ctx.get()


class RequestTracingFilter(logging.Filter):
    """Filter that dynamically injects the active request ID into the log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        req_id = get_request_id()
        record.request_id = f"[{req_id}] " if req_id else ""  # type: ignore[attr-defined]
        return True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given component name."""

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(request_id)s%(message)s"))
        handler.addFilter(RequestTracingFilter())
        logger.addHandler(handler)

    # Ensure all handlers on the logger have the tracing filter applied
    for handler in logger.handlers:
        if not any(isinstance(f, RequestTracingFilter) for f in handler.filters):
            handler.addFilter(RequestTracingFilter())

    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger
