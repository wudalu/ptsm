from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def _add_logger_name(
    logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    event_dict.setdefault("logger", getattr(logger, "name", str(logger)))
    return event_dict


def configure_logging(log_level: str | Any = "INFO") -> None:
    """Configure structlog to emit JSON logs to stdout."""
    resolved_log_level = getattr(log_level, "log_level", log_level)
    level_name = str(resolved_log_level).upper().strip()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.add_log_level,
            _add_logger_name,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )


def get_logger(name: str):
    """Return a structlog logger for the given component name."""
    return structlog.get_logger().bind(logger=name)
