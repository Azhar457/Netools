"""
Thread-safe runtime state manager (state.json).
"""

import json
import threading
from typing import Dict, Any, Optional
from netools.config import STATE_FILE

_state_lock = threading.Lock()

def load_state() -> Dict[str, Any]:
    """Load runtime state.json safely."""
    with _state_lock:
        if not STATE_FILE.exists():
            return {"instances": {}, "updated_at": "", "pac_status": "inactive"}
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"instances": {}, "updated_at": "", "pac_status": "inactive"}

def save_state(state: Dict[str, Any]) -> None:
    """Save runtime state.json safely."""
    with _state_lock:
        try:
            tmp_file = STATE_FILE.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
            tmp_file.replace(STATE_FILE)
        except Exception as e:
            print(f"[ERROR] Failed to save state: {e}")

def get_active_instances() -> Dict[str, Any]:
    """Retrieve instances dictionary from state."""
    state = load_state()
    return state.get("instances", {})

def update_instance(name: str, instance_data: Dict[str, Any]) -> None:
    """Add or update a single instance record."""
    state = load_state()
    if "instances" not in state:
        state["instances"] = {}
    state["instances"][name] = instance_data
    save_state(state)

def remove_instance(name: str) -> None:
    """Remove a single instance record."""
    state = load_state()
    if "instances" in state and name in state["instances"]:
        del state["instances"][name]
        save_state(state)
