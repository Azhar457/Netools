"""
Watchdog Service: Periodic health checks & auto-heal loop for proxy instances.
"""

import time
import threading
from typing import Callable, Optional
from netools.config import MONITOR_DEFAULT_INTERVAL, SOCKS5_PORT_START
from netools.libs.net import test_socks_upstream, is_port_open
from netools.state import load_state, update_instance, remove_instance
from netools.adapters import singbox as sb_drv
from netools.adapters import ninerouter as nr_adapt
from netools.services.proxy_service import fetch_and_parse_proxies, start_single_instance

def run_monitor_cycle(standalone: bool = False) -> int:
    """Single monitor pass: test all active instances, replace dead ones."""
    state = load_state()
    instances = state.get("instances", {})
    if not instances:
        return 0

    dead_instances = []
    for name, info in list(instances.items()):
        port = info["port"]
        if not is_port_open(port) or not test_socks_upstream(port):
            dead_instances.append((name, info))

    if not dead_instances:
        return 0

    print(f"[WATCHDOG] Found {len(dead_instances)} dead instances: {[name for name, _ in dead_instances]}")

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
                print(f"[WATCHDOG] Auto-healed slot {name} (port {port})")
                break

        if not healed:
            remove_instance(name)

    return len(dead_instances)

def run_watchdog_loop(interval: int = MONITOR_DEFAULT_INTERVAL, standalone: bool = False, stop_event: Optional[threading.Event] = None) -> None:
    """Continuous watchdog loop."""
    print(f"[WATCHDOG] Starting auto-heal watchdog every {interval}s (Standalone={standalone})...")
    while stop_event is None or not stop_event.is_set():
        try:
            run_monitor_cycle(standalone=standalone)
        except Exception as e:
            print(f"[WATCHDOG] Monitor error: {e}")
        time.sleep(interval)
