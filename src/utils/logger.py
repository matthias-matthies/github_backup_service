"""
Central logging configuration for the GitHub Backup Service.

Provides a factory function that creates consistently formatted loggers
with optional file rotation and correlation-ID context support.
"""

import logging
import logging.handlers
import os
from typing import Optional


# Global correlation ID that can be injected into every log record.
_correlation_id: str = ""


class _CorrelationIdFilter(logging.Filter):
    """Injects the current correlation_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.correlation_id = _correlation_id
        return True


def set_correlation_id(correlation_id: str) -> None:
    """Set the process-wide correlation ID used in log records.

    Args:
        correlation_id: An arbitrary string (e.g. a UUID) that identifies
                        the current backup run or request context.
    """
    global _correlation_id
    _correlation_id = correlation_id


def get_correlation_id() -> str:
    """Return the currently active correlation ID."""
    return _correlation_id


def setup_logger(
    name: str,
    log_file: Optional[str] = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Create and configure a named logger.

    The logger always gets a *console* (StreamHandler) handler.  When
    *log_file* is supplied an additional rotating file handler is attached
    (max 10 MB per file, 5 backup files kept).

    A :class:`_CorrelationIdFilter` is added to every handler so that the
    ``correlation_id`` extra field is always available to formatters.

    Args:
        name:     Logger name, typically ``__name__`` of the calling module.
        log_file: Optional filesystem path for the rotating log file.
        level:    Minimum severity level; defaults to ``logging.INFO``.

    Returns:
        A fully configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if the logger is retrieved again.
    if logger.handlers:
        return logger

    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    correlation_filter = _CorrelationIdFilter()

    # ── Console handler ──────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(fmt)
    console_handler.addFilter(correlation_filter)
    logger.addHandler(console_handler)

    # ── Optional rotating file handler ───────────────────────────────────
    if log_file:
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        file_handler.addFilter(correlation_filter)
        logger.addHandler(file_handler)

    # Prevent log records from being passed to the root logger a second time.
    logger.propagate = False

    return logger
