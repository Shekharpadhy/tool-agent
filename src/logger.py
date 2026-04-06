"""
Central logging configuration for the tool-agent.

Usage in any module:
    from src.logger import get_logger
    logger = get_logger(__name__)
    logger.info("something happened")

Log output:
  - Console  → INFO and above
  - File     → DEBUG and above  (data/logs/agent.log, rotating 1 MB × 3 backups)
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_LOGS_DIR = os.path.join(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
    "data",
    "logs",
)
_LOG_FILE = os.path.join(_LOGS_DIR, "agent.log")
_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(level: str = "INFO") -> None:
    """
    Call once at startup (in main.py) to configure the root logger.
    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _configured
    if _configured:
        return
    _configured = True

    os.makedirs(_LOGS_DIR, exist_ok=True)

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    # Console handler — INFO and above
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)

    # File handler — DEBUG and above, rotates at 1 MB, keeps 3 backups
    file_handler = RotatingFileHandler(
        _LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. setup_logging() must be called first."""
    return logging.getLogger(name)
