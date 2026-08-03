from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrafficScenario:
    """Definition for a synthetic traffic scenario."""

    name: str
    customers: tuple[str, ...]
    node_ids: tuple[str, ...]
    request_count: int
    quota: int
    randomize_nodes: bool = True
    northwind_mode: bool = False


class ScenarioFactory:
    """Factory for known traffic patterns used by the harness."""

    @staticmethod
    def northwind_scenario() -> TrafficScenario:
        return TrafficScenario(
            name="northwind",
            customers=("northwind", "alpha", "beta"),
            node_ids=("node-1", "node-2", "node-3"),
            request_count=12,
            quota=3,
            randomize_nodes=True,
            northwind_mode=True,
        )

    @staticmethod
    def mixed_customer_scenario() -> TrafficScenario:
        return TrafficScenario(
            name="mixed-customers",
            customers=("cust-a", "cust-b", "cust-c"),
            node_ids=("node-1", "node-2", "node-3"),
            request_count=15,
            quota=4,
            randomize_nodes=True,
            northwind_mode=False,
        )
