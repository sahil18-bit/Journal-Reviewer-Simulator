"""JSON structured logging using the Python standard library."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings

_STANDARD_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
    "event",
}


class JsonFormatter(logging.Formatter):
    """Render log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_FIELDS and not key.startswith("_"):
                if isinstance(value, (str, int, float, bool)) or value is None:
                    payload[key] = value
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def log_event(level: int, event: str, **fields: Any) -> None:
    """Emit a structured event; callers must never include request or manuscript bodies."""
    logging.getLogger("jrs").log(level, event, extra={"event": event, **fields})


def configure_logging(settings: Settings) -> None:
    """Configure JSON logs in every environment for easy machine parsing."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.log_level))
