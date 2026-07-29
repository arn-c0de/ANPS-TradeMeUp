"""
Database Query Caching Utilities
Redis-based caching layer for expensive database queries
"""
import hashlib
import json
import logging
import threading
from collections.abc import Callable
from functools import wraps
from typing import Any

import redis

from src.utils.redact import redact_url

logger = logging.getLogger(__name__)

# Redis is optional. Keep the probe short so a missing server costs a moment
# at first use rather than stalling every request behind it.
REDIS_CONNECT_TIMEOUT = 5


class DatabaseCache:
    """Redis cache for database queries with automatic fallback"""

    def __init__(self, url: str | None = None, enabled: bool = True):
        """
        Initialize cache

        Args:
            url: Redis connection URL. Defaults to ``settings.redis_url``, which
                is what docker-compose sets - the previous hardcoded
                ``localhost:6379`` could never reach the Redis container.
            enabled: Enable/disable caching (for testing)
        """
        self.enabled = enabled

        if not enabled:
            logger.info("Database caching is disabled")
            self.redis = None
            return

        if url is None:
            from src.config.settings import settings
            url = settings.redis_url

        try:
            self.redis = redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
                socket_keepalive=True,
            )
            # Test connection
            self.redis.ping()
            logger.info("Redis cache connected: %s", redact_url(url))
        except Exception as e:
            # Caching is an optimisation, never a requirement: fall back to
            # querying the database directly.
            logger.warning(f"Redis unavailable, caching disabled: {e}")
            self.enabled = False
            self.redis = None

    def get(self, key: str) -> Any | None:
        """
        Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/error
        """
        if not self.enabled:
            return None

        try:
            value = self.redis.get(key)
            if value:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(value)
            logger.debug(f"Cache MISS: {key}")
        except Exception as e:
            logger.error(f"Cache get error for {key}: {e}")

        return None

    def set(self, key: str, value: Any, ttl: int = 60):
        """
        Set value in cache with TTL

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time to live in seconds
        """
        if not self.enabled:
            return

        try:
            self.redis.setex(
                key,
                ttl,
                json.dumps(value, default=str)
            )
            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")

    def delete(self, pattern: str):
        """
        Delete keys matching pattern

        Args:
            pattern: Pattern to match (e.g., "stats:*")
        """
        if not self.enabled:
            return

        try:
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
                logger.info(f"Cache invalidated: {len(keys)} keys matching '{pattern}'")
        except Exception as e:
            logger.error(f"Cache delete error for pattern {pattern}: {e}")

    def invalidate_all(self):
        """Flush entire cache database"""
        if not self.enabled:
            return

        try:
            self.redis.flushdb()
            logger.warning("Entire cache database flushed!")
        except Exception as e:
            logger.error(f"Cache flush error: {e}")

    def get_stats(self) -> dict:
        """Get cache statistics"""
        if not self.enabled or not self.redis:
            return {'enabled': False}

        try:
            info = self.redis.info('stats')
            return {
                'enabled': True,
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0),
                'keys': self.redis.dbsize(),
                'memory_used': info.get('used_memory_human', 'unknown')
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {'enabled': True, 'error': str(e)}


_db_cache: DatabaseCache | None = None
_db_cache_lock = threading.Lock()


def get_db_cache() -> DatabaseCache:
    """Return the shared cache, connecting to Redis on first use.

    Deliberately lazy: connecting at import time stalled every process that
    merely imports this module for up to socket_connect_timeout seconds when
    Redis is unreachable, including test collection.
    """
    global _db_cache

    if _db_cache is None:
        with _db_cache_lock:
            if _db_cache is None:
                _db_cache = DatabaseCache(enabled=True)

    return _db_cache


class _LazyCacheProxy:
    """Module-level ``db_cache`` name that resolves on first attribute access."""

    def __getattr__(self, name):
        return getattr(get_db_cache(), name)


db_cache = _LazyCacheProxy()


# Arguments that identify a query and can be written into a key verbatim.
_KEY_SAFE_TYPES = (str, int, float, bool, type(None))

# Connections and sessions select the same data for every caller, so they carry
# no identity for the cache key and are deliberately ignored.
_IGNORED_ARG_TYPES = ("Session", "Engine", "Connection", "scoped_session")


def _key_fragment(value: Any) -> str | None:
    """Render one argument for the cache key.

    Returns None for arguments that carry no identity (database handles), and
    a stable hash for anything structured. Silently dropping a structured
    argument - as the previous version did - made two different queries share
    one cache entry.
    """
    if isinstance(value, _KEY_SAFE_TYPES):
        return repr(value)

    if type(value).__name__ in _IGNORED_ARG_TYPES:
        return None

    try:
        blob = json.dumps(value, sort_keys=True, default=repr)
    except Exception:
        blob = repr(value)
    return "#" + hashlib.blake2b(blob.encode(), digest_size=8).hexdigest()


def cached_query(key_prefix: str, ttl: int = 60):
    """
    Decorator for caching database queries.

    The decorated function must return JSON-compatible data: results round-trip
    through JSON, so a Dash component or a plotly Figure will not survive.
    Fetch plain data here and render it outside the cache.

    Usage:
        @cached_query(key_prefix="stats:metrics", ttl=30)
        def get_statistics(engine):
            # Expensive query...
            return results

    Args:
        key_prefix: Prefix for cache key
        ttl: Time to live in seconds

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Every argument that identifies the query goes into the key.
            key_parts = [key_prefix, func.__name__]

            for arg in args:
                fragment = _key_fragment(arg)
                if fragment is not None:
                    key_parts.append(fragment)

            for name, value in sorted(kwargs.items()):
                fragment = _key_fragment(value)
                if fragment is not None:
                    key_parts.append(f"{name}={fragment}")

            cache_key = ":".join(key_parts)

            cached = db_cache.get(cache_key)
            if cached is not None:
                return cached

            result = func(*args, **kwargs)

            # Store in cache (only if result is not None)
            if result is not None:
                db_cache.set(cache_key, result, ttl)

            return result

        # Add cache control methods to function
        wrapper.cache_invalidate = lambda: db_cache.delete(f"{key_prefix}:*")
        wrapper.cache_key_prefix = key_prefix

        return wrapper

    return decorator


# Convenience function for manual cache invalidation
def invalidate_cache_pattern(pattern: str):
    """
    Manually invalidate cache keys matching pattern

    Usage:
        invalidate_cache_pattern("stats:*")
        invalidate_cache_pattern("entities:top:*")
    """
    db_cache.delete(pattern)
