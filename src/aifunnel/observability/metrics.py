import threading
from collections import defaultdict


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)

    def inc(self, name: str, *, labels: dict[str, str] | None = None, value: float = 1.0) -> None:
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            self._counters[key] += value

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            items = list(self._counters.items())
        for (name, labels), value in sorted(items):
            if labels:
                label_str = ",".join(f'{k}="{v}"' for k, v in labels)
                lines.append(f"{name}{{{label_str}}} {value}")
            else:
                lines.append(f"{name} {value}")
        return "\n".join(lines) + ("\n" if lines else "")


metrics = MetricsRegistry()
