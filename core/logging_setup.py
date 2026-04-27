"""
core.logging_setup
------------------
Structured logging. Same configuration is used by the API server and CLI so
log output is identical regardless of entry point.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from core.config import get_settings

_CONFIGURED = False


def setup_logging() -> None:
    """Idempotent — safe to call from multiple entry points."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    os.makedirs(settings.log_dir, exist_ok=True)

    fmt = "%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    root.handlers.clear()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    root.addHandler(stream)

    file_h = RotatingFileHandler(
        os.path.join(settings.log_dir, "app.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_h.setFormatter(formatter)
    root.addHandler(file_h)

    # Quieten noisy libraries
    for noisy in ("urllib3", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
