"""Thin Redis wrapper for application-level caching (NL-search, etc.).

Reuses the same ``REDIS_URL`` that Celery already depends on.
The module exposes a singleton ``get_redis()`` callable so that
consumers never have to worry about connection lifecycle.
"""

import os
import logging
import redis

logger = logging.getLogger(__name__)

REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

NL_SEARCH_TTL: int = int(os.getenv("NL_SEARCH_TTL", "1800"))

_pool: redis.ConnectionPool | None = None


def get_redis() -> redis.Redis:
    """Return a Redis client backed by a shared connection pool."""
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)
        logger.info("[redis_client] Connection pool created for %s", REDIS_URL)
    return redis.Redis(connection_pool=_pool)
