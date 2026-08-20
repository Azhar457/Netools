from netools.libs.logger import get_logger

log = get_logger(__name__)

"""
9Router AI Gateway REST API Adapter (Fail-Safe with Complete proxyPoolId Unlink).
"""

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from netools.config import NINEROUTER_URL, get_ninerouter_token
from netools.middlewares.backend_guard import safe_backend_call

_CURRENT_URL = NINEROUTER_URL
_CURRENT_TOKEN = None  # lazy-loaded on first API call
_HEALTH_TTL = 3.0
_health_cache: Dict[str, Any] = {"val": None, "ts": 0.0}

def set_credentials(url: Optional[str] = None, token: Optional[str] = None) -> None:
    """Dynamically update 9Router API endpoint and authentication token."""
    global _CURRENT_URL, _CURRENT_TOKEN
    if url is not None:
        _CURRENT_URL = url.rstrip("/")
    if token is not None:
        _CURRENT_TOKEN = token

def api_request(method: str, path: str, body: Optional[Dict[str, Any]] = None, timeout: float = 5.0, max_retries: int = 2) -> Dict[str, Any]:
    """Send authenticated HTTP request to 9Router REST API with retry on transient network error."""
    global _CURRENT_TOKEN
    if _CURRENT_TOKEN is None:
        _CURRENT_TOKEN = get_ninerouter_token()
    url = f"{_CURRENT_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"}
    if _CURRENT_TOKEN:
        headers["x-9r-cli-token"] = _CURRENT_TOKEN

    last_err = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers=headers
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                import time
                time.sleep(0.3 * (2 ** attempt))

    return {"error": str(last_err)}


@safe_backend_call(fallback_return=False)
def is_healthy() -> bool:
    """Check if 9Router is currently alive and reachable (cached for _HEALTH_TTL seconds)."""
    now = time.monotonic()
    if _health_cache["val"] is not None and (now - _health_cache["ts"]) < _HEALTH_TTL:
        return _health_cache["val"]
    res = api_request("GET", "/api/proxy-pools")
    healthy = "error" not in res
    _health_cache["val"] = healthy
    _health_cache["ts"] = now
    return healthy

@safe_backend_call(fallback_return=[])
def get_connections() -> List[Dict[str, Any]]:
    """Retrieve all provider connections from 9Router."""
    res = api_request("GET", "/api/providers")
    return res.get("connections", [])

@safe_backend_call(fallback_return={})
def get_existing_pools() -> Dict[str, str]:
    """Retrieve existing 9Router proxy pools: {name: id}."""
    res = api_request("GET", "/api/proxy-pools")
    pools = res.get("proxyPools", res.get("proxy_pools", []))
    return {p["name"]: p["id"] for p in pools}

@safe_backend_call(fallback_return=None)
def assign_proxy_to_connection(conn_id: str, proxy_url: str) -> Optional[Dict[str, Any]]:
    """Assign a proxy URL to a connection."""
    res = api_request("PUT", f"/api/providers/{conn_id}", {
        "connectionProxyEnabled": True,
        "connectionProxyUrl": proxy_url,
        "connectionNoProxy": "localhost,127.0.0.1",
    })
    return res.get("connection") if "connection" in res else None

def remove_proxy_from_connection(conn_id: str) -> Optional[Dict[str, Any]]:
    """Disable proxy on a connection and completely clear proxy URL and proxyPoolId."""
    res = api_request("PUT", f"/api/providers/{conn_id}", {
        "connectionProxyEnabled": False,
        "connectionProxyUrl": "",
        "connectionNoProxy": "",
        "proxyPoolId": None,
    })
    return res.get("connection") if "connection" in res else None

def clear_all_connection_proxies() -> int:
    """Unlink and disable proxy on ALL connections in 9Router."""
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
            log.info(f"Proxy cleared: {name} ({conn['id'][:12]})")
    return cleared

clear_all_proxies = clear_all_connection_proxies

def assign_round_robin(proxies_or_pools: List[str]) -> int:
    """Distribute active proxies or pools round-robin across all 9Router connections."""
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
    """Register a new proxy pool in 9Router."""
    delete_pools_by_url(proxy_url)
    res = api_request("POST", "/api/proxy-pools", {
        "name": name,
        "proxyUrl": proxy_url,
        "noProxy": "localhost,127.0.0.1",
        "strictProxy": False,
        "isActive": True,
    })
    pool = res.get("proxyPool", {})
    return pool.get("id")

@safe_backend_call(fallback_return=False)
def delete_proxy_pool(pool_id: str) -> bool:
    """Delete proxy pool from 9Router."""
    res = api_request("DELETE", f"/api/proxy-pools/{pool_id}")
    return res.get("success", False) or "error" not in res

def delete_pools_by_url(proxy_url: str) -> None:
    """Delete all pools with matching proxy URL."""
    res = api_request("GET", "/api/proxy-pools")
    for p in res.get("proxyPools", res.get("proxy_pools", [])):
        if p.get("proxyUrl") == proxy_url:
            delete_proxy_pool(p["id"])
