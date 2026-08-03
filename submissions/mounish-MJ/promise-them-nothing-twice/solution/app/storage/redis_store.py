from __future__ import annotations

import json
import math
import threading
import time
from typing import Any

from app.storage.interfaces import QuotaStoreInterface
from app.failure_policy import FailurePolicy

try:
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None  # type: ignore[assignment]


class RedisQuotaStore(QuotaStoreInterface):
    """A Redis-backed shared-state store for customer quota usage.

    Supports both fixed-window counter and token-bucket algorithms.
    """

    _RESERVE_SCRIPT = """
local key = KEYS[1]
local customer_id = ARGV[1]
local quota = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local window_seconds = tonumber(ARGV[4])

local usage = 0
local ttl = window_seconds
local current = redis.call("GET", key)

if current then
    local ok, state = pcall(cjson.decode, current)
    if ok and type(state) == "table" and state["usage"] ~= nil then
        usage = tonumber(state["usage"]) or 0
    end

    local current_ttl = redis.call("TTL", key)
    if current_ttl and current_ttl > 0 then
        ttl = current_ttl
    end
end

if usage + quota > limit then
    return {0, usage, ttl}
end

local next_usage = usage + quota
local next_state = cjson.encode({customer_id = customer_id, usage = next_usage})
if ttl and ttl > 0 then
    redis.call("SET", key, next_state, "EX", ttl)
else
    redis.call("SET", key, next_state)
end

return {1, next_usage, ttl}
"""

    _TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local requested = tonumber(ARGV[3])
local window_seconds = tonumber(ARGV[4])

local time = redis.call("TIME")
local now = tonumber(time[1]) + tonumber(time[2]) / 1000000

local current = redis.call("HMGET", key, "tokens", "last_updated")
local tokens = tonumber(current[1])
local last_updated = tonumber(current[2])

if not tokens or not last_updated then
    tokens = capacity
    last_updated = now
else
    local elapsed = now - last_updated
    if elapsed > 0 then
        tokens = math.min(capacity, tokens + elapsed * refill_rate)
        last_updated = now
    end
end

if tokens >= requested then
    tokens = tokens - requested
    redis.call("HSET", key, "tokens", tostring(tokens), "last_updated", tostring(last_updated))
    redis.call("EXPIRE", key, window_seconds)
    return {1, tostring(tokens), 0}
else
    redis.call("HSET", key, "last_updated", tostring(last_updated))
    redis.call("EXPIRE", key, window_seconds)
    local needed = requested - tokens
    local retry_after = math.ceil(needed / refill_rate)
    return {0, tostring(tokens), retry_after}
end
"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        decode_responses: bool = True,
        failure_policy: FailurePolicy | None = None,
        algorithm: str = "fixed_window",
    ) -> None:
        self.host = host
        self.port = port
        self.db = db
        self.decode_responses = decode_responses
        self.failure_policy = failure_policy or FailurePolicy()
        self.algorithm = algorithm
        self._fallback_state: dict[str, dict[str, Any]] = {}
        self._fallback_lock = threading.Lock()
        self._client = self._create_client()

    def _create_client(self) -> Any:
        if redis is None:
            return None

        from redis.backoff import NoBackoff  # type: ignore
        from redis.retry import Retry  # type: ignore

        client = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            decode_responses=self.decode_responses,
            socket_connect_timeout=0.2,
            socket_timeout=0.2,
            retry=Retry(NoBackoff(), 0),
        )
        try:
            client.ping()
        except Exception:
            return None

        return client

    @property
    def backend_mode(self) -> str:
        return "redis" if self._client is not None else "fallback"

    def get_customer_state(self, customer_id: str) -> dict[str, Any]:
        if self._client is None:
            with self._fallback_lock:
                state = self._fallback_state.get(customer_id)
                if state is None:
                    return {}

                expires_at = state.get("expires_at")
                if expires_at is not None and time.time() >= expires_at:
                    self._fallback_state.pop(customer_id, None)
                    return {}

                return {k: v for k, v in state.items() if k != "expires_at"}

        value = self._client.get(self._customer_key(customer_id))
        if value is None:
            return {}

        if isinstance(value, bytes):
            value = value.decode("utf-8")

        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except ValueError:
                return {}
            return parsed if isinstance(parsed, dict) else {}

        return value if isinstance(value, dict) else {}

    def increment_customer_usage(self, customer_id: str, quota: int, window_seconds: int | None = None) -> dict[str, Any]:
        if self._client is None:
            with self._fallback_lock:
                state = self._fallback_state.get(customer_id)
                now = time.time()
                if state is not None:
                    expires_at = state.get("expires_at")
                    if expires_at is not None and now >= expires_at:
                        state = None

                if state is None:
                    state = {"customer_id": customer_id, "usage": 0}
                    if window_seconds is not None:
                        state["expires_at"] = now + window_seconds
                    self._fallback_state[customer_id] = state

                state["usage"] = int(state.get("usage", 0)) + int(quota)
                return {k: v for k, v in state.items() if k != "expires_at"}

        key = self._customer_key(customer_id)
        current = self._client.get(key)
        if current is None:
            current_state = {"customer_id": customer_id, "usage": 0}
            ttl = window_seconds
        else:
            current_state = json.loads(current) if isinstance(current, str) else current
            if not isinstance(current_state, dict):
                current_state = {"customer_id": customer_id, "usage": 0}
            ttl = self._client.ttl(key)
            if ttl is None or ttl < 0:
                ttl = window_seconds

        current_state["customer_id"] = customer_id
        current_state["usage"] = int(current_state.get("usage", 0)) + int(quota)
        if ttl is not None:
            self._client.set(key, json.dumps(current_state), ex=ttl)
        else:
            self._client.set(key, json.dumps(current_state))
        return current_state

    def reserve_quota(
        self,
        customer_id: str,
        quota: int,
        limit: int,
        window_seconds: int | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        quota = int(quota)
        limit = int(limit)
        win = window_seconds or 60

        if self._client is None:
            with self._fallback_lock:
                state = self._fallback_state.get(customer_id)
                now = time.time()
                if state is not None:
                    expires_at = state.get("expires_at")
                    if expires_at is not None and now >= expires_at:
                        state = None

                if state is None:
                    state = {"customer_id": customer_id}
                    if self.algorithm == "fixed_window":
                        state["usage"] = 0
                    if window_seconds is not None:
                        state["expires_at"] = now + window_seconds
                    self._fallback_state[customer_id] = state

                if self.algorithm == "token_bucket":
                    capacity = float(limit)
                    refill_rate = capacity / float(win)
                    tokens = state.get("tokens")
                    last_updated = state.get("last_updated")

                    if tokens is None or last_updated is None:
                        tokens = capacity
                        last_updated = now
                    else:
                        elapsed = now - last_updated
                        if elapsed > 0:
                            tokens = min(capacity, tokens + elapsed * refill_rate)
                            last_updated = now

                    if tokens >= quota:
                        tokens = tokens - quota
                        state["tokens"] = tokens
                        state["last_updated"] = last_updated
                        return True, {"customer_id": customer_id, "usage": int(limit - tokens)}
                    else:
                        needed = float(quota) - tokens
                        retry_after = max(1, math.ceil(needed / refill_rate))
                        state["tokens"] = tokens
                        state["last_updated"] = last_updated
                        return False, {"customer_id": customer_id, "usage": int(limit - tokens), "retry_after": retry_after}
                else:
                    usage = int(state.get("usage", 0))
                    if usage + quota > limit:
                        denied_state = {k: v for k, v in state.items() if k != "expires_at"}
                        expires_at = state.get("expires_at")
                        if expires_at is not None:
                            denied_state["retry_after"] = max(1, math.ceil(float(expires_at) - now))
                        return False, denied_state

                    state["usage"] = usage + quota
                    return True, {k: v for k, v in state.items() if k != "expires_at"}

        key = self._customer_key(customer_id)
        try:
            if self.algorithm == "token_bucket":
                capacity = float(limit)
                refill_rate = capacity / float(win)
                result = self._client.eval(
                    self._TOKEN_BUCKET_SCRIPT,
                    1,
                    key,
                    capacity,
                    refill_rate,
                    quota,
                    win,
                )
                allowed = bool(int(result[0]))
                tokens = float(result[1])
                retry_after = int(result[2])
                state = {"customer_id": customer_id, "usage": int(limit - tokens)}
                if not allowed and retry_after > 0:
                    state["retry_after"] = retry_after
                return allowed, state
            else:
                result = self._client.eval(
                    self._RESERVE_SCRIPT,
                    1,
                    key,
                    customer_id,
                    quota,
                    limit,
                    win,
                )
                allowed = bool(int(result[0]))
                usage = int(result[1])
                ttl = int(result[2])
                state = {"customer_id": customer_id, "usage": usage}
                if not allowed and ttl > 0:
                    state["retry_after"] = ttl
                return allowed, state
        except Exception as e:
            from app.observability.metrics import STORE_ERRORS
            STORE_ERRORS.labels(operation="reserve_quota").inc()
            return self.failure_policy.handle_store_failure(customer_id, e)

    def reset_customer_window(self, customer_id: str) -> None:
        if self._client is None:
            with self._fallback_lock:
                self._fallback_state.pop(customer_id, None)
            return

        self._client.delete(self._customer_key(customer_id))

    def _customer_key(self, customer_id: str) -> str:
        return f"rate_limit:{customer_id}"
