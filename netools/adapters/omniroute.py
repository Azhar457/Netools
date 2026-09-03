from netools.libs.logger import get_logger

log = get_logger(__name__)

"""
OmniRoute AI Gateway REST API Adapter (Proxy & DNS Acceleration Support).
"""

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from netools.config import OMNIROUTE_TOKEN, OMNIROUTE_URL
from netools.middlewares.backend_guard import safe_backend_call

_CURRENT_URL = OMNIROUTE_URL
_CURRENT_TOKEN = OMNIROUTE_TOKEN
_HEALTH_TTL = 3.0
_health_cache: Dict[str, Any] = {"val": None, "ts": 0.0}


def set_credentials(url: Optional[str] = None, token: Optional[str] = None) -> None:
    """Dynamically update OmniRoute API endpoint and authentication token."""
    global _CURRENT_URL, _CURRENT_TOKEN
    if url is not None:
        _CURRENT_URL = url.rstrip("/")
    if token is not None:
        _CURRENT_TOKEN = token


def api_request(
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
    timeout: float = 5.0,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """Send authenticated HTTP request to OmniRoute REST API with retry on transient network error."""
    global _CURRENT_TOKEN
    url = f"{_CURRENT_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if _CURRENT_TOKEN:
        headers["Authorization"] = f"Bearer {_CURRENT_TOKEN}"

    last_err = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(0.3 * (2**attempt))

    return {"error": str(last_err)}


@safe_backend_call(fallback_return=False)
def is_healthy() -> bool:
    """Check if OmniRoute is currently alive and reachable (cached for _HEALTH_TTL seconds)."""
    now = time.monotonic()
    if _health_cache["val"] is not None and (now - _health_cache["ts"]) < _HEALTH_TTL:
        return _health_cache["val"]
    res = api_request("GET", "/api/providers")
    healthy = "error" not in res
    _health_cache["val"] = healthy
    _health_cache["ts"] = now
    return healthy


@safe_backend_call(fallback_return=[])
def get_connections() -> List[Dict[str, Any]]:
    """Retrieve all provider connections from OmniRoute."""
    res = api_request("GET", "/api/providers")
    return res.get("connections", [])


@safe_backend_call(fallback_return={})
def get_existing_pools() -> Dict[str, str]:
    """Retrieve existing OmniRoute proxy pools: {name: id}."""
    res = api_request("GET", "/api/settings/proxies")
    proxies = res.get("proxies", res.get("items", []))
    if isinstance(proxies, list):
        return {p.get("name", p.get("id", "")): p.get("id", "") for p in proxies if isinstance(p, dict)}
    return {}


@safe_backend_call(fallback_return=None)
def assign_proxy_to_connection(conn_id: str, proxy_url: str) -> Optional[Dict[str, Any]]:
    """Assign a proxy URL to an OmniRoute provider connection."""
    res = api_request(
        "PUT",
        f"/api/providers/{conn_id}",
        {
            "connectionProxyEnabled": True,
            "connectionProxyUrl": proxy_url,
            "connectionNoProxy": "localhost,127.0.0.1",
        },
    )
    return res.get("connection") if "connection" in res else None


def remove_proxy_from_connection(conn_id: str) -> Optional[Dict[str, Any]]:
    """Disable proxy on a connection and clear proxy URL."""
    res = api_request(
        "PUT",
        f"/api/providers/{conn_id}",
        {
            "connectionProxyEnabled": False,
            "connectionProxyUrl": "",
            "connectionNoProxy": "",
            "proxyPoolId": None,
        },
    )
    return res.get("connection") if "connection" in res else None


def clear_all_connection_proxies() -> int:
    """Unlink and disable proxy on ALL connections in OmniRoute."""
    conns = get_connections()
    cleared = 0
    for conn in conns:
        spec = conn.get("providerSpecificData") or {}
        if (
            spec.get("connectionProxyEnabled")
            or conn.get("connectionProxyUrl")
            or spec.get("proxyPoolId")
            or conn.get("proxyPoolId")
        ):
            remove_proxy_from_connection(conn["id"])
            cleared += 1
            name = conn.get("name", conn.get("provider", "?"))
            log.info(f"Proxy cleared in OmniRoute: {name} ({conn['id'][:12]})")
    return cleared


clear_all_proxies = clear_all_connection_proxies


def assign_round_robin(proxies_or_pools: List[str]) -> int:
    """Distribute active proxies or pools round-robin across all OmniRoute provider connections."""
    conns = get_connections()
    if not conns or not proxies_or_pools:
        return 0
    assigned = 0
    for idx, c in enumerate(conns):
        target = proxies_or_pools[idx % len(proxies_or_pools)]
        if target.startswith("socks5://") or target.startswith("http://"):
            proxy_url = target
        else:
            proxy_url = f"socks5://127.0.0.1:{11080 + (idx % len(proxies_or_pools))}"
        res = assign_proxy_to_connection(c["id"], proxy_url)
        if res:
            assigned += 1
    return assigned


@safe_backend_call(fallback_return=None)
def add_proxy_pool(name: str, proxy_url: str) -> Optional[str]:
    """Register a new proxy entry in OmniRoute."""
    res = api_request(
        "POST",
        "/api/settings/proxies",
        {
            "name": name,
            "url": proxy_url,
            "type": "custom",
            "active": True,
        },
    )
    return res.get("id") or res.get("proxy", {}).get("id")


@safe_backend_call(fallback_return=False)
def delete_proxy_pool(pool_id: str) -> bool:
    """Delete a proxy entry from OmniRoute."""
    res = api_request("DELETE", f"/api/settings/proxies/{pool_id}")
    return res.get("success", False) or "error" not in res


def benchmark_api_dns(
    hostname: str = "api.openai.com",
    dns_servers: Optional[List[str]] = None,
    timeout: float = 1.0,
) -> Dict[str, float]:
    """Benchmark DNS resolution latency for an upstream AI provider host across multiple DNS servers."""
    if dns_servers is None:
        dns_servers = ["1.1.1.1", "8.8.8.8", "9.9.9.9", "127.0.0.1"]

    results: Dict[str, float] = {}
    for server in dns_servers:
        start = time.perf_counter()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout)
            query = _build_dns_query(hostname)
            sock.sendto(query, (server, 53))
            _data, _ = sock.recvfrom(512)
            latency_ms = (time.perf_counter() - start) * 1000.0
            results[server] = round(latency_ms, 2)
            sock.close()
        except Exception:
            results[server] = -1.0
    return results


def _build_dns_query(host: str) -> bytes:
    """Construct a minimalist standard DNS query packet for A record."""
    packet = bytearray()
    packet.extend(b"\xaa\xbb\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00")
    for part in host.split("."):
        packet.append(len(part))
        packet.extend(part.encode("ascii"))
    packet.append(0)
    packet.extend(b"\x00\x01\x00\x01")
    return bytes(packet)
