"""
Backend Guard Middleware: Suppresses errors and falls back to standalone mode if 9Router/OmniRoute is down.
"""

from functools import wraps
from typing import Any, Callable

from netools.libs.logger import get_logger

log = get_logger(__name__)

def safe_backend_call(fallback_return: Any = None):
    """Decorator to protect backend operations from crashing core proxy workflows."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log.warning(f"Backend operation '{func.__name__}' skipped: {e}")
                return fallback_return
        return wrapper
    return decorator
