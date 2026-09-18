from app.services.rate_limiter import MemoryRateLimiter, RedisRateLimiter


def test_memory_allows_up_to_limit_then_rejects() -> None:
    limiter = MemoryRateLimiter(limit=2, window_seconds=60)

    assert limiter.allow("key-a") == (True, 1)
    assert limiter.allow("key-a") == (True, 0)
    assert limiter.allow("key-a") == (False, 0)


def test_memory_keys_are_tracked_independently() -> None:
    limiter = MemoryRateLimiter(limit=1, window_seconds=60)

    assert limiter.allow("key-a") == (True, 0)
    assert limiter.allow("key-a") == (False, 0)
    assert limiter.allow("key-b") == (True, 0)


def test_memory_window_expiry_restores_allowance() -> None:
    limiter = MemoryRateLimiter(limit=2, window_seconds=0)

    for _ in range(10):
        allowed, _ = limiter.allow("key-a")
        assert allowed is True


class FakeRedis:
    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def expire(self, key: str, seconds: int) -> int:
        self.expirations[key] = seconds
        return 1


def _make_redis_limiter(monkeypatch, now: list[float]) -> tuple[RedisRateLimiter, FakeRedis]:
    monkeypatch.setattr("app.services.rate_limiter.time.time", lambda: now[0])
    client = FakeRedis()
    limiter = RedisRateLimiter(limit=2, window_seconds=60, redis_url="redis://localhost:6379")
    limiter._client = client
    return limiter, client


class RaisingRedis:
    def incr(self, key: str) -> int:
        raise ConnectionError("redis down")

    def expire(self, key: str, seconds: int) -> int:
        raise ConnectionError("redis down")


def test_redis_fails_open_when_backend_unavailable(monkeypatch) -> None:
    now = [1000.0]
    monkeypatch.setattr("app.services.rate_limiter.time.time", lambda: now[0])
    limiter = RedisRateLimiter(limit=2, window_seconds=60, redis_url="redis://localhost:6379")
    limiter._client = RaisingRedis()

    allowed, remaining = limiter.allow("key-a")

    assert allowed is True
    assert remaining == 2


def test_redis_fixed_window_limits(monkeypatch) -> None:
    now = [1000.0]
    limiter, client = _make_redis_limiter(monkeypatch, now)

    assert limiter.allow("key-a") == (True, 1)
    assert limiter.allow("key-a") == (True, 0)
    assert limiter.allow("key-a") == (False, 0)
    assert list(client.expirations.values()) == [60]


def test_redis_new_window_resets_counters(monkeypatch) -> None:
    now = [1000.0]
    limiter, _client = _make_redis_limiter(monkeypatch, now)

    assert limiter.allow("key-a") == (True, 1)
    assert limiter.allow("key-a") == (True, 0)
    assert limiter.allow("key-a") == (False, 0)

    now[0] = 1061.0
    assert limiter.allow("key-a") == (True, 1)
    assert limiter.allow("key-a") == (True, 0)