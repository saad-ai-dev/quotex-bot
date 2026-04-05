import logging
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """Structured log formatter with timestamp, level, and module."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        level = record.levelname.ljust(8)
        module = record.name
        message = record.getMessage()

        formatted = f"{timestamp} | {level} | {module} | {message}"

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            formatted += f"\n{record.exc_text}"

        return formatted


def get_logger(name: str) -> logging.Logger:
    """Get a structured logger for the given module name."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False

    return logger
