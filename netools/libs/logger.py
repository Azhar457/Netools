"""
Unified Structured Logging Module for Netools Suite.
Provides formatted, colorized terminal output and persistent log file rotation.
"""

import sys
import logging
from pathlib import Path
from typing import Optional
from netools.config import LOGS_DIR

LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "netools.log"

class ColoredFormatter(logging.Formatter):
    """Custom ANSI colored formatter for CLI output."""
    COLORS = {
        logging.DEBUG: "\033[0;36m",    # Cyan
        logging.INFO: "\033[0;32m",     # Green
        logging.WARNING: "\033[1;33m",  # Yellow
        logging.ERROR: "\033[0;31m",    # Red
        logging.CRITICAL: "\033[1;31m", # Bold Red
    }
    NC = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.NC)
        lvl = f"{color}[{record.levelname}]{self.NC}"
        msg = super().format(record)
        return f"{lvl} {record.getMessage()}"

def get_logger(name: str = "netools") -> logging.Logger:
    """Obtain configured logger instance."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Console Handler
    c_handler = logging.StreamHandler(sys.stdout)
    c_handler.setLevel(logging.INFO)
    c_handler.setFormatter(ColoredFormatter("%(message)s"))
    logger.addHandler(c_handler)

    # File Handler
    try:
        f_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
        f_handler.setLevel(logging.DEBUG)
        f_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s")
        f_handler.setFormatter(f_formatter)
        logger.addHandler(f_handler)
    except Exception:
        pass

    return logger

log = get_logger("netools")
