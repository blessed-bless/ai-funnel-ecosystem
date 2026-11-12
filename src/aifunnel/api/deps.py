from fastapi import Depends, Request

from aifunnel.config import Settings, get_settings
from aifunnel.security import SlidingWindowRateLimiter, client_key

_chat_limiter: SlidingWindowRateLimiter | None = None
_api_limiter: SlidingWindowRateLimiter | None = None


def get_chat_limiter(settings: Settings = Depends(get_settings)) -> SlidingWindowRateLimiter:
    global _chat_limiter
    if _chat_limiter is None:
        _chat_limiter = SlidingWindowRateLimiter(settings.chat_rate_limit_per_minute, 60.0)
    return _chat_limiter


def get_api_limiter(settings: Settings = Depends(get_settings)) -> SlidingWindowRateLimiter:
    global _api_limiter
    if _api_limiter is None:
        _api_limiter = SlidingWindowRateLimiter(settings.rate_limit_per_minute, 60.0)
    return _api_limiter


async def enforce_chat_limit(
    request: Request,
    limiter: SlidingWindowRateLimiter = Depends(get_chat_limiter),
) -> None:
    await limiter.check(client_key(request, "chat"))


async def enforce_api_limit(
    request: Request,
    limiter: SlidingWindowRateLimiter = Depends(get_api_limiter),
) -> None:
    await limiter.check(client_key(request, "api"))
