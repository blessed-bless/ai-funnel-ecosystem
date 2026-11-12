import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")
logger = logging.getLogger("aifunnel.retry")


async def with_retries(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.4,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    label: str = "op",
) -> T:
    last: BaseException | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return await fn()
        except exceptions as exc:  # noqa: PERF203 — явный retry loop
            last = exc
            if attempt >= attempts:
                break
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "retry label=%s attempt=%s/%s delay=%.2fs err=%s",
                label,
                attempt,
                attempts,
                delay,
                exc,
            )
            await asyncio.sleep(delay)
    assert last is not None
    raise last
