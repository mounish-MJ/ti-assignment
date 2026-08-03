from __future__ import annotations

from app.config import CustomerPolicy
from app.models import DecisionResult, RequestContext
from app.storage.interfaces import QuotaStoreInterface


class RateLimitService:
    """Service that applies quota policy to a request context.

    This milestone intentionally keeps the policy simple: a request is allowed
    when the customer has not exceeded the configured quota, and denied once the
    quota is exhausted.
    """

    def __init__(
        self,
        store: QuotaStoreInterface,
        quota: int = 100,
        window_seconds: int = 60,
        customer_policies: dict[str, CustomerPolicy] | None = None,
    ) -> None:
        self.store = store
        self.quota = quota
        self.window_seconds = window_seconds
        self.customer_policies = customer_policies or {}

    def evaluate_request(self, request_context: RequestContext) -> DecisionResult:
        """Evaluate a request against the shared quota store."""

        if not request_context.customer_id:
            return DecisionResult(
                allowed=False,
                reason="missing_customer_id",
                customer_id=request_context.customer_id,
                request_id=request_context.request_id,
                node_id=request_context.node_id,
            )

        policy = self._policy_for_customer(request_context.customer_id)
        limit = policy.rpm

        if hasattr(self.store, "reserve_quota"):
            allowed, metadata = self.store.reserve_quota(
                request_context.customer_id,
                1,
                limit,
                window_seconds=self.window_seconds,
            )
            remaining = self._remaining_from_metadata(metadata, limit)
            if not allowed:
                return DecisionResult(
                    allowed=False,
                    reason="quota_exceeded",
                    customer_id=request_context.customer_id,
                    request_id=request_context.request_id,
                    node_id=request_context.node_id,
                    retry_after=int(metadata.get("retry_after", self.window_seconds)),
                    limit=limit,
                    remaining=remaining,
                    policy=policy.policy,
                    exception_applied=policy.exception,
                )
            return DecisionResult(
                allowed=True,
                reason="allowed",
                customer_id=request_context.customer_id,
                request_id=request_context.request_id,
                node_id=request_context.node_id,
                limit=limit,
                remaining=remaining,
                policy=policy.policy,
                exception_applied=policy.exception,
            )

        state = self.store.get_customer_state(request_context.customer_id)
        usage = int(state.get("usage", 0))

        if usage >= limit:
            return DecisionResult(
                allowed=False,
                reason="quota_exceeded",
                customer_id=request_context.customer_id,
                request_id=request_context.request_id,
                node_id=request_context.node_id,
                retry_after=self.window_seconds,
                limit=limit,
                remaining=0,
                policy=policy.policy,
                exception_applied=policy.exception,
            )

        next_state = self.store.increment_customer_usage(
            request_context.customer_id,
            1,
            window_seconds=self.window_seconds,
        )
        remaining = self._remaining_from_metadata(next_state, limit)
        return DecisionResult(
            allowed=True,
            reason="allowed",
            customer_id=request_context.customer_id,
            request_id=request_context.request_id,
            node_id=request_context.node_id,
            limit=limit,
            remaining=remaining,
            policy=policy.policy,
            exception_applied=policy.exception,
        )

    def _policy_for_customer(self, customer_id: str) -> CustomerPolicy:
        return self.customer_policies.get(
            customer_id,
            CustomerPolicy(rpm=self.quota, policy="default", exception=False),
        )

    def _remaining_from_metadata(self, metadata: dict[str, object], limit: int) -> int | None:
        usage = metadata.get("usage")
        if usage is None:
            return None
        return max(0, limit - int(usage))
