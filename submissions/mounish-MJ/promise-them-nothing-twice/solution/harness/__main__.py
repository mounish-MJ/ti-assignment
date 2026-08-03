from __future__ import annotations

import argparse
import json
import os

from app.config import load_config
from app.middleware import RateLimitMiddleware
from app.services import RateLimitService
from app.storage import RedisQuotaStore
from harness.load_harness import LoadHarness, ScenarioConfig
from harness.scenarios import ScenarioFactory


DEFAULT_NODE_IDS = ("node-1", "node-2", "node-3")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the RelayAPI rate limiter load harness.",
    )
    parser.add_argument(
        "--redis-host",
        default=os.getenv("REDIS_HOST", "localhost"),
        help="Redis host for shared quota state.",
    )
    parser.add_argument(
        "--redis-port",
        type=int,
        default=int(os.getenv("REDIS_PORT", "6379")),
        help="Redis port for shared quota state.",
    )
    parser.add_argument(
        "--redis-db",
        type=int,
        default=int(os.getenv("REDIS_DB", "0")),
        help="Redis database index for shared quota state.",
    )
    parser.add_argument(
        "--config",
        default=os.getenv("RATE_LIMIT_CONFIG_PATH"),
        help="Path to rate limiter config. Defaults to config/default.yaml.",
    )
    parser.add_argument(
        "--quota",
        type=int,
        default=3,
        help="Per-customer quota for the synthetic scenario.",
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=12,
        help="Total request count to simulate.",
    )
    parser.add_argument(
        "--scenario",
        choices=["custom", "northwind", "mixed-customers"],
        default="custom",
        help="Predefined scenario to run.",
    )
    parser.add_argument(
        "--customer-id",
        default="cust-harness",
        help="Customer ID used for custom scenarios.",
    )
    parser.add_argument(
        "--node-ids",
        default=",".join(DEFAULT_NODE_IDS),
        help="Comma-separated node IDs used by the harness.",
    )
    parser.add_argument(
        "--no-randomize-nodes",
        action="store_true",
        help="Disable random node selection for request routing.",
    )
    return parser.parse_args()


def build_scenario(args: argparse.Namespace) -> type[ScenarioConfig]:
    if args.scenario == "northwind":
        return ScenarioFactory.northwind_scenario()
    if args.scenario == "mixed-customers":
        return ScenarioFactory.mixed_customer_scenario()

    return ScenarioConfig(
        customer_id=args.customer_id,
        quota=args.quota,
        request_count=args.requests,
        node_ids=tuple(item.strip() for item in args.node_ids.split(",") if item.strip()),
    )


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    store = RedisQuotaStore(
        host=args.redis_host,
        port=args.redis_port,
        db=args.redis_db,
        decode_responses=True,
    )
    service = RateLimitService(store=store, quota=args.quota, customer_policies=config.customers)
    middleware = RateLimitMiddleware(service)
    harness = LoadHarness(middleware)
    scenario = build_scenario(args)

    report = harness.run_scenario(scenario)
    print("Load harness report")
    print("--------------------")
    print(report["summary"])
    print()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
