"""Logging configuration for ShapeBridge CLI.

Provides consistent structured logging setup across the application.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List

import structlog


def configure_logging(
    level: str = "INFO",
    enable_colors: bool = True,
    enable_json: bool = False,
    extra_processors: List[Any] | None = None,
) -> None:
    """Configure structured logging for ShapeBridge.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        enable_colors: Enable colored output for console
        enable_json: Use JSON output format
        extra_processors: Additional structlog processors
    """
    # Set standard library logging level
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper()),
    )

    # Build processor chain
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="ISO"),
    ]

    if extra_processors:
        processors.extend(extra_processors)

    # Choose renderer based on output format
    if enable_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(colors=enable_colors and sys.stdout.isatty())
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        logger_factory=structlog.WriteLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Get a configured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def log_context(**kwargs: Any) -> Dict[str, Any]:
    """Create logging context dictionary.

    Args:
        **kwargs: Context key-value pairs

    Returns:
        Context dictionary for structured logging
    """
    return kwargs


# Predefined log levels and configurations
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Default configuration for different environments
CONFIGS = {
    "development": {
        "level": "DEBUG",
        "enable_colors": True,
        "enable_json": False,
    },
    "production": {
        "level": "INFO",
        "enable_colors": False,
        "enable_json": True,
    },
    "testing": {
        "level": "WARNING",
        "enable_colors": False,
        "enable_json": False,
    },
}