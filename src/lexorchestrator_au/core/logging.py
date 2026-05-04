import logging
import sys
from datetime import UTC, datetime


class JsonLikeFormatter(logging.Formatter):
    """Small structured formatter without forcing a logging vendor."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "trace_id"):
            payload["trace_id"] = record.trace_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return " ".join(f"{k}={v!r}" for k, v in payload.items())


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLikeFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
