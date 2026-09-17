from app.services.rate_limiter import RateLimiter


def test_allows_up_to_limit_then_rejects() -> None:
    limiter = RateLimiter(limit=2, window_seconds=60)

    assert limiter.allow("key-a") == (True, 1)
    assert limiter.allow("key-a") == (True, 0)
    assert limiter.allow("key-a") == (False, 0)


def test_keys_are_tracked_independently() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60)

    assert limiter.allow("key-a") == (True, 0)
    assert limiter.allow("key-a") == (False, 0)
    assert limiter.allow("key-b") == (True, 0)


def test_window_expiry_restores_allowance() -> None:
    limiter = RateLimiter(limit=2, window_seconds=0)

    for _ in range(10):
        allowed, _ = limiter.allow("key-a")
        assert allowed is True