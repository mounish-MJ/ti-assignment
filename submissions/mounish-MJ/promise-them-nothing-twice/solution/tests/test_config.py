from pathlib import Path

import pytest

from app.config import Config, CustomerPolicy, load_config
from app.logger import get_logger


def test_load_config_from_default_file():
    config_path = Path("config/default.yaml")
    config = load_config(config_path)

    assert isinstance(config, Config)
    assert config.default_rpm == 100
    assert config.window_seconds == 60
    assert config.strict_mode is True
    assert config.customer_overrides == {}
    assert config.customers["acme"] == CustomerPolicy(rpm=100, policy="contracted_standard")
    assert config.customers["northwind"] == CustomerPolicy(rpm=300, policy="contracted_enterprise")


def test_load_config_supports_auditable_customer_exception(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
default_rpm: 100
customers:
  northwind:
    rpm: 1200
    policy: approved_batch_exception
    exception: true
    audit_reason: renewal-approved temporary batch relief
""",
        encoding="utf-8",
    )

    config = load_config(config_file)

    assert config.customers["northwind"] == CustomerPolicy(
        rpm=1200,
        policy="approved_batch_exception",
        exception=True,
        audit_reason="renewal-approved temporary batch relief",
    )


def test_load_config_rejects_exception_without_audit_reason(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
customers:
  northwind:
    rpm: 1200
    policy: approved_batch_exception
    exception: true
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires audit_reason"):
        load_config(config_file)


def test_logger_initializes_with_name():
    logger = get_logger("milestone1")

    assert logger.name == "milestone1"
