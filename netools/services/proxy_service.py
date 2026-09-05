from netools.libs.logger import get_logger

log = get_logger(__name__)

"""
Proxy Service: High-speed parallel proxy fetching, testing, sing-box lifecycle, and backend sync.
"""

import concurrent.futures
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from netools.adapters import ninerouter as nr_adapt
from netools.adapters import omniroute as or_adapt
from netools.adapters import singbox as sb_drv
from netools.config import (
    CONFIGS_DIR,
    HTTP_PORT_OFFSET,
    LOGS_DIR,
    MAX_INSTANCES,
    PID_DIR,
    PROXY_SOURCES,
    RUNTIME_DIR,
    SOCKS5_PORT_START,
    STATE_FILE,
)
from netools.libs.net import fetch_text, is_port_open, probe_socks_upstream, wait_for_port
from netools.libs.parsers import extract_all_proxies
from netools.state import load_state, save_state


def fetch_and_parse_proxies(max_count: int = 250) -> List[Dict[str, Any]]:
    """Fetch raw subscriptions from sources concurrently with cache fallback and protocol interleaving."""
    import json
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cache_file = RUNTIME_DIR / "last_known_proxies.json"
    failed_sources = 0

    per_source_limit = max(max_count // max(len(PROXY_SOURCES), 1) * 2, 80)

    def _fetch_source(url: str) -> tuple[bool, List[Dict[str, Any]]]:
        for attempt in range(2):
            try:
                raw = fetch_text(url, timeout=3.5)
                return True, extract_all_proxies(raw, max_count=per_source_limit)
            except Exception as e:
                if attempt == 1:
                    log.warning(f"Failed fetching source {url}: {e}")
                time.sleep(0.15)
        return False, []

    source_results: List[List[Dict[str, Any]]] = []

    # Parallel fetch of all sources simultaneously
    with ThreadPoolExecutor(max_workers=min(len(PROXY_SOURCES), 6)) as ex:
        futures = [ex.submit(_fetch_source, url) for url in PROXY_SOURCES]
        for f in as_completed(futures):
            try:
                success, candidates = f.result()
                if not success:
                    failed_sources += 1
                elif candidates:
                    source_results.append(candidates)
            except Exception:
                failed_sources += 1

    # Interleave results across sources to maximize protocol & subnet diversity
    all_proxies = []
    seen = set()
    max_len = max((len(c) for c in source_results), default=0)
    for i in range(max_len):
        for s_list in source_results:
            if i < len(s_list):
                p = s_list[i]
                key = f"{p['server']}:{p['server_port']}"
                if key not in seen:
                    seen.add(key)
                    all_proxies.append(p)

    if all_proxies:
        try:
            cache_file.write_text(json.dumps(all_proxies, indent=2), encoding="utf-8")
        except Exception:
            pass
        return all_proxies[:max_count]

    # Offline / Fallback recovery from cache only if ALL remote sources failed
    if failed_sources == len(PROXY_SOURCES) and cache_file.exists():
        try:
            log.warning("All remote proxy sources failed; falling back to local proxy cache")
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if isinstance(cached, list):
                return cached[:max_count]
        except Exception:
            pass

    return all_proxies[:max_count]


def start_proxy_pool(max_instances: int = MAX_INSTANCES, standalone: bool = False) -> Dict[str, Any]:
    """Start full proxy pool with high-speed parallel testing, multi-round replenishment, and backend sync."""
    log.info("Stopping old instances...")
    stop_proxy_pool(standalone=standalone)

    log.info("Downloading fresh proxy configs...")
    candidate_pool = fetch_and_parse_proxies(max_count=max(max_instances * 15, 300))
    log.info(f"Parsed {len(candidate_pool)} unique candidate proxies")

    # Multi-round adaptive replenishment
    verified_alive: Dict[int, tuple[str, Dict[str, Any], Any]] = {}  # port -> (name, proxy, proc)
    slot_diagnostics: Dict[int, str] = {}  # port -> final reason
    slot_meta: Dict[int, tuple[str, Dict[str, Any]]] = {}  # port -> (name, proxy) for all attempts
    cand_idx = 0
    max_rounds = 4

    for _round_num in range(1, max_rounds + 1):
        unfilled_slots = [
            i for i in range(max_instances)
            if (SOCKS5_PORT_START + i) not in verified_alive
        ]
        if not unfilled_slots or cand_idx >= len(candidate_pool):
            break

        round_slots: Dict[int, tuple[str, Dict[str, Any], Any, str]] = {}
        for slot in unfilled_slots:
            if cand_idx >= len(candidate_pool):
                break
            port = SOCKS5_PORT_START + slot
            name = f"sb-{slot:02d}"
            proxy = candidate_pool[cand_idx]
            cand_idx += 1
            config = sb_drv.build_singbox_config(proxy, port)
            proc = sb_drv.start_singbox_instance(name, config)
            reason = "alive" if proc else "spawn_failed"
            round_slots[port] = (name, proxy, proc, reason)
            slot_meta[port] = (name, proxy)  # record meta even if spawn failed

        if not round_slots:
            break

        # Fast parallel port readiness poll
        pending_ports = set(round_slots.keys())
        deadline = time.monotonic() + 1.5
        while pending_ports and time.monotonic() < deadline:
            ready = {p for p in pending_ports if is_port_open(p, timeout=0.03)}
            pending_ports -= ready
            if not pending_ports:
                break
            time.sleep(0.03)

        # Parallel Upstream Testing
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(len(round_slots), 1)) as ex:
            futs = {
                ex.submit(probe_socks_upstream, port, timeout=3.5): port
                for port in round_slots
            }
            for future in concurrent.futures.as_completed(futs):
                port = futs[future]
                name, proxy, proc, _ = round_slots[port]
                try:
                    if future.result():
                        verified_alive[port] = (name, proxy, proc)
                        slot_diagnostics[port] = "alive"
                    else:
                        proc.kill()
                        slot_diagnostics[port] = "upstream_probe_failed"
                except Exception as exc:
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    slot_diagnostics[port] = f"probe_exception:{type(exc).__name__}"
                # Always record the slot attempt (alive or dead) for diagnostics
                slot_meta[port] = (name, proxy)

        if len(verified_alive) >= max_instances:
            break

    # Sort verified instances by port number
    alive_items = [
        (verified_alive[p][0], p, verified_alive[p][1], verified_alive[p][2])
        for p in sorted(verified_alive.keys())
    ]

    state = {"instances": {}, "updated_at": datetime.now().isoformat()}
    active_count = 0

    # Batch register pools to OmniRoute & 9Router
    omni_pools_batch = []
    nr_pools_batch = []
    for idx, (_, port, _, _) in enumerate(alive_items):
        pool_name = f"free-proxy-{idx}"
        socks_url = f"socks5://127.0.0.1:{port}"
        omni_pools_batch.append((pool_name, socks_url))
        nr_pools_batch.append((pool_name, socks_url))

    omni_pool_ids: Dict[str, str] = {}
    nr_pool_ids: Dict[str, str] = {}
    if not standalone and alive_items:
        if or_adapt.is_healthy():
            omni_pool_ids = or_adapt.add_proxy_pools_batch(omni_pools_batch)
        if nr_adapt.is_healthy():
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
                f_map = {ex.submit(nr_adapt.add_proxy_pool, p_name, p_url): p_name for p_name, p_url in nr_pools_batch}
                for f in concurrent.futures.as_completed(f_map):
                    p_name = f_map[f]
                    try:
                        pid = f.result()
                        if pid:
                            nr_pool_ids[p_name] = pid
                    except Exception:
                        pass

    for name, port, proxy, proc in alive_items:
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        socks_url = f"socks5://127.0.0.1:{port}"
        http_url = f"http://127.0.0.1:{port + HTTP_PORT_OFFSET}"
        pool_name = f"free-proxy-{active_count}"
        pool_id = nr_pool_ids.get(pool_name)
        omni_pool_id = omni_pool_ids.get(pool_name)

        state["instances"][name] = {
            "name": name,
            "pid": proc.pid,
            "port": port,
            "http_port": port + HTTP_PORT_OFFSET,
            "proxy_type": proxy["type"],
            "server": proxy["server"],
            "server_port": proxy.get("server_port", 0),
            "socks_url": socks_url,
            "http_url": http_url,
            "pool_id": pool_id,
            "omni_pool_id": omni_pool_id,
            "pool_name": pool_name,
            "started_at": now_str,
            "reason": "alive",
        }
        active_count += 1
        pool_str = f" → pool {pool_name}" if (pool_id or omni_pool_id) else (" (standalone)" if standalone else "")
        log.info(f"{name}: {proxy['type']} → {proxy['server']}:{proxy.get('server_port', '')} → port {port}{pool_str}")

    # Record diagnostics for slots that were attempted but did not come up alive.
    # Operators need to see WHY a proxy failed (spawn, probe, exception) not just
    # the count of failures.
    alive_ports = {p for _, p, _, _ in alive_items}
    for port, (name, proxy) in slot_meta.items():
        if port in alive_ports:
            continue
        reason = slot_diagnostics.get(port, "unknown")
        state["instances"][name] = {
            "name": name,
            "port": port,
            "http_port": port + HTTP_PORT_OFFSET,
            "proxy_type": proxy["type"],
            "server": proxy["server"],
            "server_port": proxy.get("server_port", 0),
            "pool_name": None,
            "started_at": None,
            "reason": reason,
        }
        log.info(f"{name} [{reason}]: {proxy['type']} → {proxy['server']}:{proxy.get('server_port', '')} → port {port}")

    # Assign proxy to 9Router / OmniRoute connections using ONLY verified alive ports
    if not standalone and active_count > 0:
        alive_socks_urls = [f"socks5://127.0.0.1:{port}" for _, port, _, _ in alive_items]
        if or_adapt.is_healthy():
            conns = or_adapt.get_connections()
            or_assignments = []
            for idx, c in enumerate(conns):
                p_url = alive_socks_urls[idx % len(alive_socks_urls)]
                or_assignments.append((c["id"], p_url))
            assigned_count = or_adapt.assign_proxies_to_connections_batch(or_assignments)
            log.info(f"OmniRoute: {assigned_count}/{len(conns)} connections bound to proxy pool (atomic)")

        if nr_adapt.is_healthy():
            conns = nr_adapt.get_connections()
            nr_assignments = []
            for idx, c in enumerate(conns):
                p_url = alive_socks_urls[idx % len(alive_socks_urls)]
                nr_assignments.append((c["id"], p_url))
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
                f_list = [ex.submit(nr_adapt.assign_proxy_to_connection, cid, url) for cid, url in nr_assignments]
                concurrent.futures.wait(f_list, timeout=4.0)
            log.info(f"9Router: {len(conns)} connections bound to proxy pool (concurrent)")

    save_state(state)
    mode_str = " (Standalone Mode)" if standalone else " → Active Gateway Proxy Pool"
    log.info(f"{active_count} proxies active{mode_str}")
    return state


def stop_proxy_pool(standalone: bool = False) -> None:
    """Stop all instances, wipe state and scratch files, and cleanly unlink gateway pools."""
    sb_drv.stop_all_singbox_instances()

    if not standalone:
        if nr_adapt.is_healthy():
            log.info("Clearing proxy from all 9Router connections...")
            nr_adapt.clear_all_connection_proxies()
            pools = nr_adapt.get_existing_pools()
            for name, pool_id in pools.items():
                if name.startswith("free-proxy-"):
                    nr_adapt.delete_proxy_pool(pool_id)
                    print(f"Deleted 9Router pool: {name}")

        if or_adapt.is_healthy():
            log.info("Clearing proxy from all OmniRoute connections and pools...")
            or_adapt.clear_all_connection_proxies()
            or_adapt.clear_managed_pools()

    # Wipe scratch files
    for f in CONFIGS_DIR.glob("*.json"):
        f.unlink(missing_ok=True)
    for f in PID_DIR.glob("*.pid"):
        f.unlink(missing_ok=True)
    for f in LOGS_DIR.glob("*.log"):
        f.unlink(missing_ok=True)

    STATE_FILE.unlink(missing_ok=True)
    log.info("All cleaned up")


def refresh_proxy_pool(max_instances: int = MAX_INSTANCES, standalone: bool = False) -> Dict[str, Any]:
    """Stop and restart proxy pool."""
    stop_proxy_pool(standalone=standalone)
    return start_proxy_pool(max_instances=max_instances, standalone=standalone)


def get_proxy_status() -> Dict[str, Any]:
    """Check live status of proxy instances."""
    state = load_state()
    instances = state.get("instances", {})
    results = []

    for name, info in instances.items():
        alive = is_port_open(info["port"])
        results.append(
            {
                "name": name,
                "port": info["port"],
                "http_port": info.get("http_port", info["port"] + HTTP_PORT_OFFSET),
                "server": info["server"],
                "proxy_type": info["proxy_type"],
                "dns": info.get("dns", "⚡ Remote SOCKS5h"),
                "started_at": info.get("started_at", "?"),
                "alive": alive,
            }
        )
    return {"total": len(results), "alive_count": sum(1 for r in results if r["alive"]), "instances": results}


def start_single_instance(
    name: str, port: int, proxy: Dict[str, Any], standalone: bool = False, pool_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Start and test a single instance (used by auto-heal watchdog)."""
    config = sb_drv.build_singbox_config(proxy, port)
    proc = sb_drv.start_singbox_instance(name, config)
    if not proc:
        return None
    wait_for_port(port, timeout=3.0)
    if not probe_socks_upstream(port):
        try:
            proc.kill()
        except Exception:
            pass
        return None

    socks_url = f"socks5://127.0.0.1:{port}"
    http_url = f"http://127.0.0.1:{port + HTTP_PORT_OFFSET}"
    pool_id = None
    omni_pool_id = None
    if not standalone and pool_name:
        if nr_adapt.is_healthy():
            pool_id = nr_adapt.add_proxy_pool(pool_name, socks_url)
        if or_adapt.is_healthy():
            omni_pool_id = or_adapt.add_proxy_pool(pool_name, socks_url)

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    return {
        "name": name,
        "pid": proc.pid,
        "port": port,
        "http_port": port + HTTP_PORT_OFFSET,
        "proxy_type": proxy["type"],
        "server": proxy["server"],
        "server_port": proxy.get("server_port", 0),
        "socks_url": socks_url,
        "http_url": http_url,
        "pool_id": pool_id,
        "omni_pool_id": omni_pool_id,
        "pool_name": pool_name,
        "started_at": now_str,
    }


# ---------------------------------------------------------------------------
# Process Exit Cleanup Guard
# ---------------------------------------------------------------------------

import atexit


def _auto_cleanup_on_exit():
    """Ensure any active proxy pool, routes, and instances are cleanly released when process terminates."""
    try:
        import logging
        logging.disable(logging.CRITICAL)
        try:
            from netools.adapters import platform_proxy
            platform_proxy.disable_system_proxy()
        except Exception:
            pass
        stop_proxy_pool(standalone=False)
    except Exception:
        pass



atexit.register(_auto_cleanup_on_exit)
