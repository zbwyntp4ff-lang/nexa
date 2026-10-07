"""Logging setup for NEXA.
Configures structured, leveled logging and installs a filter that redacts
known secret patterns (API keys) so they can never end up in log output,
even if a bug elsewhere tries to log a settings object or raw header.
"""
from __future__ import annotations
import logging
import sys
from app.core.secrets import redact_secrets as _redact
class SecretRedactionFilter(logging.Filter):
    """Scrubs API-key-shaped substrings from every log record."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _redact(str(v)) for k, v in record.args.items()}
            else:
                record.args = tuple(
                    _redact(arg) if isinstance(arg, str) else arg for arg in record.args
                )
        return True
def configure_logging(level: str = "INFO") -> None:
    """Configure the root logger once for the whole application."""
    root = logging.getLogger()
    if getattr(root, "_nexa_configured", False):
        return
    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    handler.addFilter(SecretRedactionFilter())
    root.handlers = [handler]
    root.setLevel(level.upper())
    root._nexa_configured = True  # type: ignore[attr-defined]
def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
