import json
import logging
import sys
from datetime import UTC, datetime


class StructuredLogFormatter(logging.Formatter):
    """Structured JSON formatter for log aggregation pipelines."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "trace_id"):
            payload["trace_id"] = record.trace_id
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            payload["exception"] = record.exc_text
        # Merge extra fields passed via `extra={...}` in log calls
        for key in ("trace_id", "path", "duration_ms", "provider", "attempt", "url"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredLogFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())
