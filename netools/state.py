"""
Thread-safe and process-safe runtime state manager (state.json).
"""

import json
import os
import sys
import threading
from typing import Any, Dict

from netools.config import STATE_FILE
from netools.libs.logger import get_logger

log = get_logger(__name__)

_state_lock = threading.RLock()

def _acquire_file_lock(f):
    """Acquire an exclusive file lock (cross-platform)."""
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

def _release_file_lock(f):
    """Release the file lock (cross-platform)."""
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def load_state() -> Dict[str, Any]:
    """Load runtime state.json safely with file-level locking."""
    with _state_lock:
        if not STATE_FILE.exists():
            return {"instances": {}, "updated_at": "", "pac_status": "inactive"}
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                _acquire_file_lock(f)
                try:
                    data = json.load(f)
                finally:
                    _release_file_lock(f)
                return data
        except Exception:
            return {"instances": {}, "updated_at": "", "pac_status": "inactive"}

def save_state(state: Dict[str, Any]) -> None:
    """Save runtime state.json safely with atomic write and file locking."""
    with _state_lock:
        try:
            tmp_file = STATE_FILE.with_suffix(".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                _acquire_file_lock(f)
                try:
                    json.dump(state, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                finally:
                    _release_file_lock(f)
            tmp_file.replace(STATE_FILE)
        except Exception as e:
            log.error(f"Failed to save state: {e}")

def get_active_instances() -> Dict[str, Any]:
    """Retrieve instances dictionary from state."""
    state = load_state()
    return state.get("instances", {})

def update_instance(name: str, instance_data: Dict[str, Any]) -> None:
    """Add or update a single instance record."""
    with _state_lock:
        state = load_state()
        if "instances" not in state:
            state["instances"] = {}
        state["instances"][name] = instance_data
        save_state(state)

def remove_instance(name: str) -> None:
    """Remove a single instance record."""
    with _state_lock:
        state = load_state()
        if "instances" in state and name in state["instances"]:
            del state["instances"][name]
            save_state(state)
