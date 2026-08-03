from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CustomerPolicy:
    """Configured quota policy for a customer."""

    rpm: int
    policy: str
    exception: bool = False
    audit_reason: str | None = None


@dataclass(frozen=True)
class Config:
    """Runtime configuration for the rate limiter."""

    default_rpm: int
    window_seconds: int
    strict_mode: bool
    customer_overrides: dict[str, int]
    customers: dict[str, CustomerPolicy]
    algorithm: str = "fixed_window"


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration from a YAML file.

    Parameters
    ----------
    path:
        Path to the YAML configuration file. If omitted, the default config is used.
    """

    config_path = Path(path or "config/default.yaml")
    with config_path.open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = yaml.safe_load(handle) or {}

    return Config(
        default_rpm=int(data.get("default_rpm", 100)),
        window_seconds=int(data.get("window_seconds", 60)),
        strict_mode=bool(data.get("strict_mode", True)),
        customer_overrides=dict(data.get("customer_overrides", {})),
        customers=_load_customer_policies(data.get("customers", {})),
        algorithm=str(data.get("algorithm", "fixed_window")),
    )


def _load_customer_policies(raw_customers: Any) -> dict[str, CustomerPolicy]:
    if raw_customers is None:
        return {}
    if not isinstance(raw_customers, dict):
        raise ValueError("customers must be a mapping")

    customers: dict[str, CustomerPolicy] = {}
    for customer_id, raw_policy in raw_customers.items():
        if not isinstance(customer_id, str) or not customer_id:
            raise ValueError("customer IDs must be non-empty strings")
        if not isinstance(raw_policy, dict):
            raise ValueError(f"customer policy for {customer_id} must be a mapping")

        rpm = int(raw_policy.get("rpm"))
        if rpm <= 0:
            raise ValueError(f"customer policy for {customer_id} must have a positive rpm")

        policy = str(raw_policy.get("policy", "contracted"))
        exception = bool(raw_policy.get("exception", False))
        audit_reason = raw_policy.get("audit_reason")
        if audit_reason is not None:
            audit_reason = str(audit_reason)
        if exception and not audit_reason:
            raise ValueError(f"customer policy for {customer_id} requires audit_reason when exception is true")

        customers[customer_id] = CustomerPolicy(
            rpm=rpm,
            policy=policy,
            exception=exception,
            audit_reason=audit_reason,
        )

    return customers
