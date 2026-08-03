from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from app.middleware.limiter_middleware import RateLimitMiddleware
from app.nodes.node_app import NodeRuntime
from harness.scenarios import TrafficScenario


@dataclass(frozen=True)
class ScenarioConfig:
    """Configuration for a small load scenario."""

    customer_id: str
    quota: int
    request_count: int
    node_ids: tuple[str, ...] = ("node-1", "node-2", "node-3")


class LoadHarness:
    """A synthetic load harness for the rate limiter.

    The harness runs a sequential scenario across multiple customers and node
    runtimes. It simulates randomized routing and boundary behavior, but it is
    not a concurrency proof.
    """

    def __init__(self, middleware: RateLimitMiddleware) -> None:
        self.middleware = middleware

    def run_scenario(self, config: ScenarioConfig | TrafficScenario) -> dict[str, Any]:
        """Run a scenario and return a readable report."""

        if isinstance(config, TrafficScenario):
            scenario = config
            customers = scenario.customers
            node_ids = scenario.node_ids
            request_count = scenario.request_count
            quota = scenario.quota
            randomize_nodes = scenario.randomize_nodes
            northwind_mode = scenario.northwind_mode
        else:
            scenario = None
            customers = (config.customer_id,)
            node_ids = config.node_ids
            request_count = config.request_count
            quota = config.quota
            randomize_nodes = True
            northwind_mode = False

        runtimes = [NodeRuntime(self.middleware, node_id=node_id) for node_id in node_ids]
        allowed = 0
        denied = 0
        boundary_hits = 0
        failures = []
        customer_reports: dict[str, dict[str, Any]] = {
            customer_id: {
                "allowed": 0,
                "denied": 0,
                "boundary_hits": 0,
                "failures": [],
                "limit": None,
                "policy": None,
                "exception_applied": False,
            }
            for customer_id in customers
        }

        customer_sequence: list[str]
        if northwind_mode and "northwind" in customers:
            # The Northwind scenario should simulate repeated overage by a single
            # customer while still exercising other customer boundaries.
            other_customers = [c for c in customers if c != "northwind"]
            if len(other_customers) >= 2 and request_count >= 4:
                customer_sequence = ["northwind"] * (request_count - 2) + other_customers[:2]
            else:
                customer_sequence = [customers[index % len(customers)] for index in range(request_count)]
        else:
            customer_sequence = [customers[index % len(customers)] for index in range(request_count)]

        for index in range(request_count):
            customer_id = customer_sequence[index]
            if randomize_nodes:
                node = runtimes[random.randrange(len(runtimes))]
            else:
                node = runtimes[index % len(runtimes)]

            payload = {
                "customer_id": customer_id,
                "request_id": f"req-{index}",
            }
            if northwind_mode and customer_id == "northwind":
                payload["request_id"] = f"northwind-{index}"

            response = node.handle_request(payload)
            customer_report = customer_reports.setdefault(
                customer_id,
                {
                    "allowed": 0,
                    "denied": 0,
                    "boundary_hits": 0,
                    "failures": [],
                    "limit": None,
                    "policy": None,
                    "exception_applied": False,
                },
            )
            if response.get("limit") is not None:
                customer_report["limit"] = response["limit"]
            if response.get("policy") is not None:
                customer_report["policy"] = response["policy"]
            customer_report["exception_applied"] = bool(response.get("exception_applied", False))

            if response["status"] == "accepted":
                allowed += 1
                customer_report["allowed"] += 1
            else:
                denied += 1
                customer_report["denied"] += 1
                if response["reason"] == "quota_exceeded":
                    boundary_hits += 1
                    customer_report["boundary_hits"] += 1
                failure = {"request_id": payload["request_id"], "customer_id": customer_id, "reason": response["reason"]}
                failures.append(failure)
                customer_report["failures"].append(failure)

        return {
            "scenario_name": getattr(scenario, "name", "custom"),
            "customers": list(customers),
            "quota": quota,
            "request_count": request_count,
            "allowed": allowed,
            "denied": denied,
            "boundary_hits": boundary_hits,
            "failures": failures,
            "customer_reports": customer_reports,
            "node_ids": list(node_ids),
            "randomized_nodes": randomize_nodes,
            "northwind_mode": northwind_mode,
            "execution_model": "sequential",
            "summary": self._build_summary(allowed, denied, boundary_hits, failures, customer_reports),
        }

    def _build_summary(
        self,
        allowed: int,
        denied: int,
        boundary_hits: int,
        failures: list[dict[str, Any]],
        customer_reports: dict[str, dict[str, Any]],
    ) -> str:
        lines = [
            f"Allowed requests: {allowed}",
            f"Denied requests: {denied}",
            f"Quota boundary hits: {boundary_hits}",
            f"Failure reasons: {', '.join(sorted({failure['reason'] for failure in failures})) or 'none'}",
            "Execution model: sequential",
        ]
        for customer_id in sorted(customer_reports):
            report = customer_reports[customer_id]
            lines.append(
                "Customer "
                f"{customer_id}: allowed={report['allowed']} denied={report['denied']} "
                f"limit={report['limit']} policy={report['policy']} "
                f"exception_applied={report['exception_applied']}"
            )
        return "\n".join(lines)
