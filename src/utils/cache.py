"""
Database Query Caching Utilities
Redis-based caching layer for expensive database queries
"""
import redis
import json
from typing import Optional, Any, Callable
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class DatabaseCache:
    """Redis cache for database queries with automatic fallback"""

    def __init__(self, host='localhost', port=6379, db=0, enabled=True):
        """
        Initialize cache

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            enabled: Enable/disable caching (for testing)
        """
        self.enabled = enabled

        if not enabled:
            logger.info("Database caching is disabled")
            self.redis = None
            return

        try:
            self.redis = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            # Test connection
            self.redis.ping()
            logger.info(f"Redis cache connected: {host}:{port}/{db}")
        except Exception as e:
            logger.warning(f"Redis unavailable, caching disabled: {e}")
            self.enabled = False
            self.redis = None

    def get(self, key: str) -> Optional[Any]:
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


# Global cache instance
db_cache = DatabaseCache(enabled=True)


def cached_query(key_prefix: str, ttl: int = 60):
    """
    Decorator for caching database queries

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
            # Build cache key from function name and arguments
            # Note: Only use hashable arguments for key
            key_parts = [key_prefix, func.__name__]

            # Add simple args to key (skip complex objects like engine)
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    key_parts.append(str(arg))

            # Add simple kwargs to key
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (str, int, float, bool)):
                    key_parts.append(f"{k}={v}")

            cache_key = ":".join(key_parts)

            # Try cache first
            cached = db_cache.get(cache_key)
            if cached is not None:
                return cached

            # Cache miss - execute function
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
