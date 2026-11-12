import logging

logger = logging.getLogger("aifunnel.redis")

_redis = None
_redis_url: str | None = None


async def get_redis(url: str | None):
    """Ленивый Redis. None url → None клиент."""
    global _redis, _redis_url
    if not url:
        return None
    if _redis is not None and _redis_url == url:
        return _redis
    try:
        from redis.asyncio import Redis
    except ImportError:
        logger.warning("пакет redis не установлен — rate-limit остаётся in-memory")
        return None
    _redis = Redis.from_url(url, decode_responses=True)
    _redis_url = url
    try:
        await _redis.ping()
    except Exception as exc:
        logger.warning("redis ping failed: %s", exc)
        await _redis.aclose()
        _redis = None
        _redis_url = None
        return None
    return _redis


async def close_redis() -> None:
    global _redis, _redis_url
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        _redis_url = None
