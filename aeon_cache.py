"""
AEON OS — Cache layer with Redis and in-memory fallback.
=========================================================
Provides a simple key/value cache that prefers Redis when available but
silently falls back to an in-memory LRU cache so the backend keeps working
during local development or when Redis is unreachable.

Env:
  AEON_REDIS_URL       redis://host:port/db (default: none)
  AEON_CACHE_TTL       default TTL in seconds (default: 300)
"""

import hashlib
import json
import logging
import os
from functools import wraps
from typing import Any

logger = logging.getLogger("aeon_cache")

# Optional Redis import; the backend works without it.
try:
    import redis
except ImportError:  # pragma: no cover
    redis = None  # type: ignore


def _make_key(prefix: str, *parts: Any) -> str:
    """Build a deterministic cache key from a prefix and parts."""
    hashed = hashlib.sha256(
        "|".join(str(p) for p in parts).encode("utf-8")
    ).hexdigest()[:32]
    return f"{prefix}:{hashed}"


class Cache:
    """Simple cache with Redis backend and in-memory fallback."""

    def __init__(self, url: str | None = None, default_ttl: int | None = None):
        self.url = url or os.environ.get("AEON_REDIS_URL", "")
        self.default_ttl = int(default_ttl or os.environ.get("AEON_CACHE_TTL", "300"))
        self._local: dict[str, Any] = {}
        self._redis = None
        if redis is None:
            logger.debug("redis package not installed; using in-memory cache")
            return
        if not self.url:
            logger.debug("AEON_REDIS_URL not set; using in-memory cache")
            return
        try:
            self._redis = redis.from_url(self.url, socket_connect_timeout=1, socket_timeout=1)
            self._redis.ping()
            logger.info("Connected to Redis at %s", self.url)
        except Exception as exc:  # pragma: no cover
            logger.warning("Redis unavailable (%s); falling back to in-memory cache", exc)
            self._redis = None

    def get(self, key: str, default: Any = None) -> Any:
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                if raw is not None:
                    return json.loads(raw.decode("utf-8"))
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis get failed for %s: %s", key, exc)
        return self._local.get(key, default)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        ttl = ttl or self.default_ttl
        if self._redis is not None:
            try:
                self._redis.setex(key, ttl, json.dumps(value, default=str))
                return
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis set failed for %s: %s", key, exc)
        self._local[key] = value

    def delete(self, key: str) -> None:
        if self._redis is not None:
            try:
                self._redis.delete(key)
                return
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis delete failed for %s: %s", key, exc)
        self._local.pop(key, None)

    def clear(self) -> None:
        self._local.clear()
        if self._redis is not None:
            try:
                self._redis.flushdb()
            except Exception as exc:  # pragma: no cover
                logger.warning("Redis flushdb failed: %s", exc)


# Singleton cache instance used across the backend.
_cache: Cache | None = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache


def cached(prefix: str, ttl: int | None = None):
    """Decorator that caches the result of a function using the shared cache.

    The cache key is built from the prefix and the positional/keyword arguments.
    Only supports JSON-serializable return values.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = _make_key(prefix, func.__name__, args, kwargs)
            cache = get_cache()
            value = cache.get(key)
            if value is not None:
                return value
            value = func(*args, **kwargs)
            cache.set(key, value, ttl=ttl)
            return value
        return wrapper
    return decorator
