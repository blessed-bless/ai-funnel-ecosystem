import logging
import sys
from typing import Any


class _JsonishFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            base["request_id"] = request_id
        if record.exc_info:
            base["exc"] = self.formatException(record.exc_info)
        # Одна строка — удобно грепать в journald/docker logs
        parts = [f'{k}={_quote(v)}' for k, v in base.items()]
        return " ".join(parts)


def _quote(value: Any) -> str:
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    if " " in text or "=" in text:
        return f'"{text}"'
    return text


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level.upper())
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonishFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
