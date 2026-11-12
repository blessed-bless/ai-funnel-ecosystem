from fastapi import Depends, Request

from aifunnel.config import Settings, get_settings
from aifunnel.security import client_key
from aifunnel.security.rate_limit import (
    RateLimiter,
    RedisSlidingWindowRateLimiter,
    SlidingWindowRateLimiter,
)
from aifunnel.security.redis_client import get_redis

_chat_limiter: RateLimiter | None = None
_api_limiter: RateLimiter | None = None
_limiter_backend: str | None = None


async def _build_limiter(settings: Settings, *, limit: int, prefix: str) -> RateLimiter:
    redis = await get_redis(settings.redis_url or None)
    if redis is not None:
        return RedisSlidingWindowRateLimiter(redis, limit, 60.0, prefix=prefix)
    return SlidingWindowRateLimiter(limit, 60.0)


async def get_chat_limiter(settings: Settings = Depends(get_settings)) -> RateLimiter:
    global _chat_limiter, _limiter_backend
    backend = "redis" if settings.redis_url else "memory"
    if _chat_limiter is None or _limiter_backend != backend:
        _chat_limiter = await _build_limiter(
            settings, limit=settings.chat_rate_limit_per_minute, prefix="rl:chat"
        )
        _limiter_backend = backend
    return _chat_limiter


async def get_api_limiter(settings: Settings = Depends(get_settings)) -> RateLimiter:
    global _api_limiter, _limiter_backend
    backend = "redis" if settings.redis_url else "memory"
    if _api_limiter is None or _limiter_backend != backend:
        _api_limiter = await _build_limiter(
            settings, limit=settings.rate_limit_per_minute, prefix="rl:api"
        )
        _limiter_backend = backend
    return _api_limiter


def reset_limiters() -> None:
    global _chat_limiter, _api_limiter, _limiter_backend
    _chat_limiter = None
    _api_limiter = None
    _limiter_backend = None


async def enforce_chat_limit(
    request: Request,
    limiter: RateLimiter = Depends(get_chat_limiter),
) -> None:
    await limiter.check(client_key(request, "chat"))


async def enforce_api_limit(
    request: Request,
    limiter: RateLimiter = Depends(get_api_limiter),
) -> None:
    await limiter.check(client_key(request, "api"))
