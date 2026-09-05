from netools.libs.logger import get_logger

log = get_logger(__name__)

"""
Watchdog Service: Periodic health checks & auto-heal loop for proxy instances.
"""

import threading
import time
from typing import Optional

from netools.adapters import ninerouter as nr_adapt
from netools.adapters import singbox as sb_drv
from netools.config import MONITOR_DEFAULT_INTERVAL, SOCKS5_PORT_START
from netools.libs.net import is_port_open, probe_socks_upstream
from netools.services.proxy_service import fetch_and_parse_proxies, start_single_instance
from netools.state import load_state, remove_instance, update_instance


def run_monitor_cycle(standalone: bool = False) -> int:
    """Single monitor pass: test all active instances, replace dead ones."""
    state = load_state()
    instances = state.get("instances", {})

    # Kill switch restore: if a kill switch is armed and the pool has
    # recovered (at least one alive instance), disarm the firewall block.
    restore_fn = state.get("_kill_switch_restore")
    if restore_fn is not None:
        alive_count = sum(
            1 for info in instances.values() if info.get("reason") == "alive"
        )
        if alive_count > 0:
            try:
                restore_fn()
                log.info("kill_switch disarmed: proxy recovered, outbound restored")
            except Exception as e:
                log.warning(f"kill_switch disarm failed: {e}")
            finally:
                state["_kill_switch_restore"] = None
                from netools.state import save_state
                save_state(state)

    if not instances:
        return 0

    dead_instances = []
    for name, info in list(instances.items()):
        port = info["port"]
        if not is_port_open(port) or not probe_socks_upstream(port):
            dead_instances.append((name, info))

    if not dead_instances:
        return 0

    log.info(f"Found {len(dead_instances)} dead instances: {[name for name, _ in dead_instances]}")

    fresh_proxies = fetch_and_parse_proxies(max_count=len(dead_instances) * 2)
    p_idx = 0

    for name, old_info in dead_instances:
        port = old_info["port"]
        pool_name = old_info.get("pool_name", f"free-proxy-{port - SOCKS5_PORT_START}")

        sb_drv.stop_singbox_instance(name)
        if not standalone and old_info.get("pool_id") and nr_adapt.is_healthy():
            nr_adapt.delete_proxy_pool(old_info["pool_id"])

        healed = False
        while p_idx < len(fresh_proxies):
            cand = fresh_proxies[p_idx]
            p_idx += 1
            info = start_single_instance(name, port, cand, standalone=standalone, pool_name=pool_name)
            if info:
                update_instance(name, info)
                healed = True
                log.info(f"Auto-healed slot {name} (port {port})")
                break

        if not healed:
            remove_instance(name)

    return len(dead_instances)


def run_watchdog_loop(
    interval: int = MONITOR_DEFAULT_INTERVAL, standalone: bool = False, stop_event: Optional[threading.Event] = None
) -> None:
    """Continuous watchdog loop."""
    log.info(f"Starting auto-heal watchdog every {interval}s (Standalone={standalone})...")
    while stop_event is None or not stop_event.is_set():
        try:
            run_monitor_cycle(standalone=standalone)
        except Exception as e:
            log.info(f"Monitor error: {e}")
        time.sleep(interval)


_watchdog_thread: Optional[threading.Thread] = None
_watchdog_stop_event: Optional[threading.Event] = None


def start_watchdog_thread(interval: int = MONITOR_DEFAULT_INTERVAL, standalone: bool = False) -> None:
    """Start the auto-heal watchdog as a daemon background thread."""
    global _watchdog_thread, _watchdog_stop_event
    if _watchdog_thread and _watchdog_thread.is_alive():
        log.info("Watchdog already running")
        return
    _watchdog_stop_event = threading.Event()
    _watchdog_thread = threading.Thread(
        target=run_watchdog_loop,
        args=(interval, standalone, _watchdog_stop_event),
        daemon=True,
        name="proxy-watchdog",
    )
    _watchdog_thread.start()


def stop_watchdog() -> None:
    """Signal the watchdog thread to stop and wait for it to exit."""
    global _watchdog_thread, _watchdog_stop_event
    if _watchdog_stop_event:
        _watchdog_stop_event.set()
    if _watchdog_thread and _watchdog_thread.is_alive():
        try:
            _watchdog_thread.join(timeout=MONITOR_DEFAULT_INTERVAL + 5)
        except Exception:
            pass
    _watchdog_thread = None
    _watchdog_stop_event = None
    log.info("Watchdog stopped")


def is_watchdog_running() -> bool:
    """Return True if the auto-heal watchdog daemon thread is alive."""
    return bool(_watchdog_thread and _watchdog_thread.is_alive())

