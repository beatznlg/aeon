"""Tests for aeon_server.RateLimiter."""

from aeon_server import RateLimiter


def test_rate_limiter_allows_under_limit():
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    key = "test-client"
    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is True


def test_rate_limiter_blocks_over_limit():
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    key = "test-client"
    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is True
    assert limiter.is_allowed(key) is False


def test_rate_limiter_tracks_keys_independently():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    assert limiter.is_allowed("client-a") is True
    assert limiter.is_allowed("client-b") is True
    assert limiter.is_allowed("client-a") is False
    assert limiter.is_allowed("client-b") is False


def test_rate_limiter_sliding_window_expires_old_requests():
    import time

    limiter = RateLimiter(max_requests=1, window_seconds=0)
    key = "client"
    assert limiter.is_allowed(key) is True
    # With a 0-second window, the next request should be allowed after a tiny sleep.
    time.sleep(0.01)
    assert limiter.is_allowed(key) is True
