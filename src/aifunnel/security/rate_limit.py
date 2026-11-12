import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Protocol

from fastapi import HTTPException, Request, status

logger = logging.getLogger("aifunnel.ratelimit")


class RateLimiter(Protocol):
    async def check(self, key: str) -> None: ...


class SlidingWindowRateLimiter:
    """In-memory limiter — один процесс."""

    def __init__(self, limit: int, window_seconds: float) -> None:
        self.limit = max(1, limit)
        self.window = max(1.0, window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        now = time.monotonic()
        async with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > self.window:
                bucket.popleft()
            if len(bucket) >= self.limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Слишком много запросов. Подожди немного и повтори.",
                )
            bucket.append(now)


class RedisSlidingWindowRateLimiter:
    """Общий лимит на несколько реплик через Redis ZSET."""

    def __init__(self, redis_client, limit: int, window_seconds: float, *, prefix: str = "rl") -> None:
        self._redis = redis_client
        self.limit = max(1, limit)
        self.window = max(1.0, window_seconds)
        self.prefix = prefix

    async def check(self, key: str) -> None:
        now = time.time()
        member = f"{now}:{time.time_ns()}"
        redis_key = f"{self.prefix}:{key}"
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - self.window)
        pipe.zadd(redis_key, {member: now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, int(self.window) + 1)
        try:
            results = await pipe.execute()
        except Exception as exc:
            logger.warning("redis rate-limit unavailable, fail-open: %s", exc)
            return
        count = int(results[2])
        if count > self.limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Слишком много запросов. Подожди немного и повтори.",
            )


def client_key(request: Request, prefix: str = "ip") -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else "unknown"
    return f"{prefix}:{ip}"
