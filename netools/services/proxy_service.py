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


def fetch_and_parse_proxies(max_count: int = MAX_INSTANCES) -> List[Dict[str, Any]]:
    """Fetch raw subscriptions from sources with retry and local cache fallback."""
    import json

    all_proxies = []
    seen = set()
    failed_sources = 0
    cache_file = RUNTIME_DIR / "last_known_proxies.json"

    for url in PROXY_SOURCES:
        source_success = False
        for attempt in range(2):
            try:
                raw = fetch_text(url)
                parsed = extract_all_proxies(raw, max_count=max_count)
                for p in parsed:
                    key = f"{p['server']}:{p['server_port']}"
                    if key not in seen:
                        seen.add(key)
                        all_proxies.append(p)
                        if len(all_proxies) >= max_count:
                            break
                source_success = True
                break  # Success on this source
            except Exception as e:
                if attempt == 1:
                    log.warning(f"Failed fetching source {url}: {e}")
                time.sleep(0.5)
        if not source_success:
            failed_sources += 1

    if all_proxies:
        # Cache last-known-good proxies
        try:
            cache_file.write_text(json.dumps(all_proxies, indent=2), encoding="utf-8")
        except Exception:
            pass
        return all_proxies

    # Offline/Fallback recovery from cache if ALL network sources failed
    if failed_sources == len(PROXY_SOURCES) and cache_file.exists():
        try:
            log.warning("All remote proxy sources failed; falling back to local proxy cache")
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if isinstance(cached, list):
                return cached[:max_count]
        except Exception:
            pass

    return all_proxies


def start_proxy_pool(max_instances: int = MAX_INSTANCES, standalone: bool = False) -> Dict[str, Any]:
    """Start full proxy pool with high-speed parallel testing and backend sync."""
    log.info("Stopping old instances...")
    stop_proxy_pool(standalone=standalone)

    log.info("Downloading fresh proxy configs...")
    proxies = fetch_and_parse_proxies(max_instances)
    log.info(f"Parsed {len(proxies)} unique candidate proxies")

    started = []  # (name, port, proxy, proc)
    for i, proxy in enumerate(proxies[:max_instances]):
        port = SOCKS5_PORT_START + i
        name = f"sb-{i:02d}"
        config = sb_drv.build_singbox_config(proxy, port)
        proc = sb_drv.start_singbox_instance(name, config)
        if proc:
            started.append((name, port, proxy, proc))

    # Wait for instances to start listening (poll-based, max 3s)
    for _, port, _, _ in started:
        wait_for_port(port, timeout=3.0)

    # Parallel Upstream Testing (All 20 instances tested concurrently)
    alive = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
        futures = {
            ex.submit(probe_socks_upstream, port): (name, port, proxy, proc) for name, port, proxy, proc in started
        }
        for future in concurrent.futures.as_completed(futures):
            name, port, proxy, proc = futures[future]
            if future.result():
                alive.append((name, port, proxy, proc))
            else:
                log.warning(f"{name} failed upstream test, killing")
                try:
                    proc.kill()
                except Exception:
                    pass

    alive.sort(key=lambda e: e[1])  # Keep sequential port order

    state = {"instances": {}, "updated_at": datetime.now().isoformat()}
    active_count = 0

    for name, port, proxy, proc in alive:
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        socks_url = f"socks5://127.0.0.1:{port}"
        http_url = f"http://127.0.0.1:{port + HTTP_PORT_OFFSET}"

        pool_name = f"free-proxy-{active_count}"
        pool_id = None
        omni_pool_id = None

        if not standalone:
            if nr_adapt.is_healthy():
                pool_id = nr_adapt.add_proxy_pool(pool_name, socks_url)
            if or_adapt.is_healthy():
                omni_pool_id = or_adapt.add_proxy_pool(pool_name, socks_url)

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
        }
        active_count += 1
        pool_str = f" → pool {pool_name}" if (pool_id or omni_pool_id) else (" (standalone)" if standalone else "")
        log.info(f"{name}: {proxy['type']} → {proxy['server']}:{proxy.get('server_port', '')} → port {port}{pool_str}")

    # Assign proxy to 9Router / OmniRoute connections
    if not standalone and active_count > 0:
        if nr_adapt.is_healthy():
            conns = nr_adapt.get_connections()
            for idx, c in enumerate(conns):
                p_idx = idx % active_count
                p_url = f"socks5://127.0.0.1:{SOCKS5_PORT_START + p_idx}"
                res = nr_adapt.assign_proxy_to_connection(c["id"], p_url)
                if res:
                    log.info(f"9Router connection {c['id'][:12]}: proxy → {p_url}")

        if or_adapt.is_healthy():
            conns = or_adapt.get_connections()
            for idx, c in enumerate(conns):
                p_idx = idx % active_count
                p_url = f"socks5://127.0.0.1:{SOCKS5_PORT_START + p_idx}"
                res = or_adapt.assign_proxy_to_connection(c["id"], p_url)
                if res:
                    log.info(f"OmniRoute connection {c['id'][:12]}: proxy → {p_url}")

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
            pools = or_adapt.get_existing_pools()
            for name, pool_id in pools.items():
                if name.startswith("free-proxy-"):
                    or_adapt.delete_proxy_pool(pool_id)
                    print(f"Deleted OmniRoute pool: {name}")

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
