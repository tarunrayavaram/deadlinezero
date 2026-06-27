"""
app/utils/logging_config.py
----------------------------
Structured logging setup for DeadlineZero.
Provides a consistent log format across all modules.
"""

import logging
import sys
from typing import Optional

from app.config import get_settings

settings = get_settings()

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: Optional[str] = None) -> None:
    """
    Configure root logger.
    Call once at application startup (main.py lifespan).
    """
    log_level = level or ("DEBUG" if settings.app_debug else "INFO")

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,
        force=True,
    )

    # Quiet noisy third-party loggers in production
    if settings.is_production:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("apscheduler").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger – import and call at the top of each module."""
    return logging.getLogger(name)
