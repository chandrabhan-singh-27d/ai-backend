import logging
import time
from collections import defaultdict, deque
from typing import Any, cast

logger = logging.getLogger("app.services.rate_limiter")


class RateLimiter:
    def allow(self, key: str) -> tuple[bool, int]:
        raise NotImplementedError


class MemoryRateLimiter(RateLimiter):
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> tuple[bool, int]:
        now = time.monotonic()
        window = self._hits[key]

        while window and now - window[0] > self.window_seconds:
            window.popleft()

        if len(window) < self.limit:
            window.append(now)
            return True, self.limit - len(window)
        return False, 0


class RedisRateLimiter(RateLimiter):
    def __init__(self, limit: int, window_seconds: int, redis_url: str = "") -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._client: Any
        import redis

        redis_client = cast(Any, redis.Redis)
        self._client = redis_client.from_url(redis_url or "redis://localhost:6379")

    def allow(self, key: str) -> tuple[bool, int]:
        window_key = f"rate:{key}:{int(time.time()) // self.window_seconds}"
        try:
            count = int(self._client.incr(window_key))
            if count == 1:
                self._client.expire(window_key, self.window_seconds)
        except Exception:
            # Fail open: an outage in the shared counter must not 500 every request
            # behind auth; log and allow until Redis recovers.
            logger.warning("redis_rate_limiter_unavailable_failing_open key=%s", key)
            return True, self.limit
        if count <= self.limit:
            return True, self.limit - count
        return False, 0


_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        from app.config import (
            RATE_LIMIT_MAX_REQUESTS,
            RATE_LIMIT_STRATEGY,
            RATE_LIMIT_WINDOW_SECONDS,
            REDIS_URL,
        )

        if RATE_LIMIT_STRATEGY == "redis":
            _limiter = RedisRateLimiter(
                limit=RATE_LIMIT_MAX_REQUESTS,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
                redis_url=REDIS_URL,
            )
        else:
            _limiter = MemoryRateLimiter(
                limit=RATE_LIMIT_MAX_REQUESTS,
                window_seconds=RATE_LIMIT_WINDOW_SECONDS,
            )
    return _limiter