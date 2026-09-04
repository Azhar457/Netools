"""
Unified Structured Logging Module for Netools Suite.
Provides formatted, colorized terminal output and persistent log file rotation.
"""

import logging
import sys
from typing import Dict

from netools.config import LOGS_DIR


class ColoredFormatter(logging.Formatter):
    """Custom ANSI colored formatter for CLI output."""

    COLORS: Dict[int, str] = {
        logging.DEBUG: "\033[0;36m",  # Cyan
        logging.INFO: "\033[0;32m",  # Green
        logging.WARNING: "\033[1;33m",  # Yellow
        logging.ERROR: "\033[0;31m",  # Red
        logging.CRITICAL: "\033[1;31m",  # Bold Red
    }
    NC = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.NC)
        lvl = f"{color}[{record.levelname}]{self.NC}"
        return f"{lvl} {super().format(record)}"


class JsonFormatter(logging.Formatter):
    """Structured JSON formatter for production log ingestion and metrics."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime

        payload = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def get_logger(name: str = "netools") -> logging.Logger:
    """Obtain configured logger instance with optional structured JSON formatting."""
    import os

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    use_json = os.getenv("NETOOLS_LOG_JSON", "0") in ("1", "true", "True")

    # Console Handler
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.INFO)
    if use_json:
        c_handler.setFormatter(JsonFormatter())
    else:
        c_handler.setFormatter(ColoredFormatter("%(message)s"))
    logger.addHandler(c_handler)

    # File Handler
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        f_handler = logging.FileHandler(str(LOGS_DIR / "netools.log"), encoding="utf-8")
        f_handler.setLevel(logging.DEBUG)
        if use_json:
            f_handler.setFormatter(JsonFormatter())
        else:
            f_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
            f_handler.setFormatter(f_formatter)
        logger.addHandler(f_handler)
    except Exception:
        pass

    return logger


log = get_logger("netools")
