import time
from dataclasses import dataclass
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class _Entry(Generic[T]):
    value: T
    expires_at: float


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: float = 5.0) -> None:
        self.ttl = max(0.1, ttl_seconds)
        self._data: dict[str, _Entry[T]] = {}
        self._lock = Lock()

    def get(self, key: str) -> T | None:
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            if entry.expires_at < now:
                self._data.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: T) -> None:
        with self._lock:
            self._data[key] = _Entry(value=value, expires_at=time.monotonic() + self.ttl)

    def invalidate(self, prefix: str = "") -> None:
        with self._lock:
            if not prefix:
                self._data.clear()
                return
            for key in [k for k in self._data if k.startswith(prefix)]:
                self._data.pop(key, None)
