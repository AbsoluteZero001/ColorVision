"""Logging setup for local console and rotating file output."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.utils.paths import get_logs_directory

LOG_FORMAT = "[%(levelname)s] %(asctime)s %(name)s: %(message)s"


def setup_logging(log_directory: Path | None = None) -> None:
    """Configure application logging once per process."""
    root_logger = logging.getLogger()
    if getattr(root_logger, "_colorvision_configured", False):
        return

    destination = log_directory or get_logs_directory()
    destination.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        destination / "colorvision.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger._colorvision_configured = True  # type: ignore[attr-defined]
